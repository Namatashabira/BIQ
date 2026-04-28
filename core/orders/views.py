from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.shortcuts import render
from django.db import transaction
from core.models import Order
from .serializers import OrderSerializer
from core.permissions import IsTenantAdmin
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
import traceback

logger = logging.getLogger('core')


def order_status_page(request):
    """Simple HTML page for users to check order status"""
    return render(request, 'order_status.html')


class UserOrderView(APIView):
    """User places an order on the frontend"""
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        """Frontend sends order data to the backend via API"""
        try:
            logger.info(f"POST /api/core/user/orders/ - IP: {request.META.get('REMOTE_ADDR')}")
            logger.info(f"Request data: {request.data}")
            
            # Validate required fields
            required_fields = ['customer_name', 'customer_email', 'phone_number', 'location']
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            
            if missing_fields:
                logger.error(f"Missing fields: {missing_fields}")
                return Response(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            order_items = request.data.get("order_items", [])
            if not order_items:
                logger.error("No order items provided")
                return Response(
                    {"error": "No order items provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate order items
            for i, item in enumerate(order_items):
                if not item.get("product_name") or item.get("quantity", 0) <= 0 or item.get("price", 0) <= 0:
                    logger.error(f"Invalid item at index {i}: {item}")
                    return Response(
                        {"error": f"Invalid item data at index {i}: {item}"}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Resolve tenant from authenticated user or tenant_uuid in payload
            tenant = None
            if request.user and request.user.is_authenticated:
                tenant = getattr(request.user, 'tenant', None)
                if not tenant:
                    from tenants.models import Tenant
                    tenant = Tenant.objects.filter(admin=request.user).first()
            if not tenant:
                tenant_uuid = request.data.get('tenant_uuid')
                if tenant_uuid:
                    from tenants.models import Tenant
                    tenant = Tenant.objects.filter(uuid=tenant_uuid).first()

            # Create single order with multiple items
            serializer = OrderSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                order = serializer.save()
                if tenant and not order.tenant:
                    order.tenant = tenant
                    order.save(update_fields=['tenant'])
                logger.info(f" Order created successfully: Order #{order.id} with {len(order_items)} items, Total: ${order.total}")
                logger.info(f" Order saved to database: customer={order.customer_name}, email={order.customer_email}, status={order.status}")
                
                # Notify admin panel
                self._notify_admin_new_order(order)
                
                # Return the created order
                response_serializer = OrderSerializer(order)
                return Response(response_serializer.data, status=status.HTTP_201_CREATED)
            else:
                logger.error(f" Order validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            logger.error(f" Unexpected error in order creation: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {"error": "Internal server error"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request):
        """User gets their orders"""
        try:
            email = request.query_params.get('email')
            status_filter = request.query_params.get('status')
            
            if not email:
                return Response(
                    {'error': 'Email parameter required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Case-insensitive email lookup, scoped to tenant
            logger.info(f"[EMAIL] Fetching orders for email: {email}")
            orders = Order.objects.filter(customer_email__iexact=email)

            # Scope to tenant if resolvable
            tenant_uuid = request.query_params.get('tenant_uuid')
            if tenant_uuid:
                from tenants.models import Tenant
                tenant = Tenant.objects.filter(uuid=tenant_uuid).first()
                if tenant:
                    orders = orders.filter(tenant=tenant)

            orders = orders.order_by('-date')
            
            if status_filter:
                orders = orders.filter(status=status_filter.lower())
            
            serializer = OrderSerializer(orders, many=True)
            logger.info(f"[SUCCESS] Found {orders.count()} orders for {email}")
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching orders: {str(e)}")
            return Response(
                {"error": "Internal server error"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _notify_admin_new_order(self, order):
        """Real-time notification to admin panel"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'admin_orders',
                {
                    'type': 'new_order',
                    'order': OrderSerializer(order).data
                }
            )
            logger.info(f"Admin notification sent successfully for order {order.id}")
        except Exception as e:
            logger.error(f"Admin notification error: {e}")


class AdminOrderView(APIView):
    """Admin sees order in the admin panel"""
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, request):
        user = request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            from tenants.models import Tenant
            tenant = Tenant.objects.filter(admin=user).first()
            if tenant:
                user.tenant = tenant
                user.save(update_fields=['tenant'])
        return tenant

    def get(self, request):
        """Admin sees orders scoped to their tenant"""
        try:
            status_filter = request.query_params.get('status')

            if request.user.is_superuser:
                orders = Order.objects.all().order_by('-date')
            else:
                tenant = self._get_tenant(request)
                if not tenant:
                    return Response([], status=status.HTTP_200_OK)
                orders = Order.objects.filter(tenant=tenant).order_by('-date')

            if status_filter:
                orders = orders.filter(status=status_filter.lower())

            serializer = OrderSerializer(orders, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error fetching admin orders: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request):
        """Admin updates order status to Confirmed or Cancelled"""
        print("=" * 50)
        print("PATCH METHOD CALLED")
        print(f"Request data: {request.data}")
        print(f"Request user: {request.user}")
        print("=" * 50)
        
        try:               
            order_id = request.data.get('id')
            new_status = request.data.get('status')

            logger.info(f"PATCH request received - order_id: {order_id}, new_status: {new_status}")
            print(f"Extracted - order_id: {order_id}, new_status: {new_status}")

            if not order_id:
                return Response(
                    {'error': 'Order ID is required'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            if new_status not in ['confirmed', 'cancelled', 'pending']:
                return Response(
                    {'error': 'Invalid status. Must be: confirmed, cancelled, or pending'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if request.user.is_superuser:
                order = Order.objects.get(id=order_id)
            else:
                tenant = self._get_tenant(request)
                if not tenant:
                    return Response({'error': 'Tenant not found'}, status=status.HTTP_403_FORBIDDEN)
                order = Order.objects.get(id=order_id, tenant=tenant)
            logger.info(f"Found order {order_id}, current status: {order.status}")

            order.status = new_status.lower()
            order.save(update_fields=['status'])
            
            logger.info(f"Order {order_id} status updated to {new_status}")

            # Try to notify user about status update (don't fail if this errors)
            try:
                self._notify_user_status_update(order)
            except Exception as notify_error:
                logger.warning(f"Failed to send notification for order {order_id}: {notify_error}")
            
            return Response(
                {'id': order.id, 'status': order.status, 'message': 'Order status updated successfully'}, 
                status=status.HTTP_200_OK
            )
            
        except Order.DoesNotExist:
            logger.error(f"Order not found: {order_id}")
            return Response(
                {'error': 'Order not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {"error": f"Internal server error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _notify_user_status_update(self, order):
        """Real-time notification to user about status update"""
        try:
            channel_layer = get_channel_layer()
            # Sanitize email for use in group name (replace @ with _at_)
            sanitized_email = order.customer_email.replace('@', '_at_').replace('.', '_')
            group_name = f'user_{sanitized_email}'
            
            print(f"📤 Attempting to send WebSocket notification:")
            print(f"   Group: {group_name}")
            print(f"   Original Email: {order.customer_email}")
            print(f"   Order ID: {order.id}")
            print(f"   Status: {order.status}")
            print(f"   Customer: {order.customer_name}")
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'status_update',
                    'order_id': order.id,
                    'status': order.status
                }
            )
            logger.info(f"✅ User notification sent successfully for order {order.id} to {order.customer_email}")
            print(f"✅ User notification sent successfully!")
        except Exception as e:
            logger.error(f"❌ User notification error for order {order.id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"❌ Failed to send notification: {e}")


@api_view(['POST'])
@permission_classes([AllowAny])
@transaction.atomic
def place_order(request):
    """Alternative @api_view endpoint for placing orders"""
    try:
        logger.info(f"POST /api/core/place-order/ - IP: {request.META.get('REMOTE_ADDR')}")
        logger.info(f"Request data: {request.data}")
        
        # Validate required fields
        required_fields = ['customer_name', 'customer_email', 'phone_number', 'location']
        missing_fields = [field for field in required_fields if not request.data.get(field)]
        
        if missing_fields:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        order_items = request.data.get("order_items", [])
        if not order_items:
            return Response(
                {"error": "No order items provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate order items
        for i, item in enumerate(order_items):
            if not item.get("product_name") or item.get("quantity", 0) <= 0 or item.get("price", 0) <= 0:
                return Response(
                    {"error": f"Invalid item data at index {i}: {item}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Create order
        serializer = OrderSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            order = serializer.save()
            logger.info(f"Order created: {order.id} with {len(order_items)} items")
            
            # Notify admin panel
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    'admin_orders',
                    {
                        'type': 'new_order',
                        'order': OrderSerializer(order).data
                    }
                )
                logger.info(f"Admin notification sent for order {order.id}")
            except Exception as e:
                logger.error(f"Admin notification error: {e}")
            
            return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Order validation failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        logger.error(f"Unexpected error in place_order: {str(e)}")
        return Response(
            {"error": "Internal server error"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )