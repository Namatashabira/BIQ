from .business_config import BusinessConfig
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.db.models import Count, Sum, Q
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone
from tenants.models import Tenant
from product.models import Product
from core.orders.models import Order
from core.orders.serializers import OrderSerializer
from core.models import (
    BusinessSettings,
    Customer,
    Receipt,
    ReceiptItem,
    AbandonedCart,
    AbandonedCartItem,
    User,
    Appointment,
    AppointmentAttendee,
    ROLE_SUPERADMIN,
    ROLE_TENANT_ADMIN,
    ROLE_WORKER,
)

logger = logging.getLogger('core')

class SuperAdminTenantSummaryView(APIView):
    """
    Superadmin overview sourced directly from the database.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.info(f"SuperAdmin summary requested from {request.META.get('REMOTE_ADDR')}")

        if getattr(request.user, 'role', None) != 'superadmin':
            return Response({'error': 'Permission denied. Superadmin role required.'}, status=status.HTTP_403_FORBIDDEN)

        tenants = Tenant.objects.all().select_related('admin')
        tenant_uuids = list(tenants.values_list('uuid', flat=True))

        # Map uuid to id for legacy lookups
        uuid_to_id = {str(t.uuid): t.id for t in tenants}
        id_to_uuid = {t.id: str(t.uuid) for t in tenants}

        user_counts = {
            id_to_uuid[row['tenant_id']]: row['user_count']
            for row in User.objects.filter(tenant_id__in=uuid_to_id.values())
            .values('tenant_id')
            .annotate(user_count=Count('id'))
        }

        product_counts = {
            id_to_uuid[row['tenant_id']]: row['product_count']
            for row in Product.objects.filter(tenant_id__in=uuid_to_id.values())
            .values('tenant_id')
            .annotate(product_count=Count('id'))
        }

        tenant_orders = Order.objects.filter(created_by__tenant_id__in=uuid_to_id.values())
        order_counts = {
            id_to_uuid[row['created_by__tenant_id']]: row['order_count']
            for row in tenant_orders
            .values('created_by__tenant_id')
            .annotate(order_count=Count('id'))
        }

        revenue_by_tenant = {
            id_to_uuid[row['created_by__tenant_id']]: float(row['revenue'] or 0)
            for row in tenant_orders
            .filter(status__in=['confirmed', 'delivered'])
            .values('created_by__tenant_id')
            .annotate(revenue=Sum('total'))
        }

        tenant_rows = []
        for tenant in tenants:
            uuid_str = str(tenant.uuid)
            tenant_rows.append({
                'uuid': uuid_str,
                'id': tenant.id,
                'name': tenant.name,
                'businessType': tenant.business_type,
                'isVerified': tenant.is_verified,
                'users': user_counts.get(uuid_str, 0),
                'products': product_counts.get(uuid_str, 0),
                'orders': order_counts.get(uuid_str, 0),
                'revenue': revenue_by_tenant.get(uuid_str, 0.0),
                'createdAt': tenant.created_at.isoformat(),
            })

        tenant_rows.sort(key=lambda row: row['revenue'], reverse=True)

        overview = {
            'total_tenants': tenants.count(),
            'verified_tenants': tenants.filter(is_verified=True).count(),
            'total_users': User.objects.count(),
            'total_orders': Order.objects.count(),
            'completed_orders': Order.objects.filter(status__in=['confirmed', 'delivered']).count(),
            'unassigned_orders': Order.objects.filter(created_by__isnull=True).count(),
            'total_revenue': float(Order.objects.filter(status__in=['confirmed', 'delivered']).aggregate(total=Sum('total'))['total'] or 0),
        }

        recent_tenants = [
            {
                'uuid': str(tenant.uuid),
                'id': tenant.id,
                'name': tenant.name,
                'businessType': tenant.business_type,
                'createdAt': tenant.created_at.isoformat(),
                'isVerified': tenant.is_verified,
            }
            for tenant in tenants.order_by('-created_at')[:5]
        ]

        return Response({
            'overview': overview,
            'tenants': tenant_rows,
            'recent_tenants': recent_tenants,
        })


class OrdersView(APIView):
    """
    Handles user orders:
    - GET /api/core/orders/?status=pending
    - POST /api/core/orders/ with order_items
    - PATCH /api/core/orders/ to update order status
    """
    permission_classes = [IsAuthenticated]

    def _resolve_tenant(self, request):
        """Resolve tenant for the authenticated user, fixing missing tenant_id on the fly."""
        user = request.user
        # Direct FK
        tenant = getattr(user, 'tenant', None)
        if not tenant and getattr(user, 'tenant_id', None):
            from tenants.models import Tenant as TenantModel
            tenant = TenantModel.objects.filter(id=user.tenant_id).first()
        # Fallback: user is admin of a tenant
        if not tenant:
            from tenants.models import Tenant as TenantModel
            tenant = TenantModel.objects.filter(admin=user).first()
            if tenant:
                user.tenant = tenant
                user.save(update_fields=['tenant'])
        # Fallback: tenant_uuid in query params (superadmin impersonation)
        if not tenant and user.is_superuser:
            tenant_uuid = request.query_params.get('tenant_uuid')
            if tenant_uuid:
                from tenants.models import Tenant as TenantModel
                tenant = TenantModel.objects.filter(uuid=tenant_uuid).first()
        return tenant

    def get(self, request):
        logger.info(f"GET /api/core/orders/ - IP: {request.META.get('REMOTE_ADDR')}")
        status_param = request.query_params.get("status")

        if request.user.is_superuser:
            orders = Order.objects.all()
        else:
            tenant = self._resolve_tenant(request)
            if not tenant:
                return Response([], status=200)
            orders = Order.objects.filter(tenant=tenant)

        if status_param:
            orders = orders.filter(status=status_param.lower())
        serializer = OrderSerializer(orders, many=True)
        logger.info(f"Returning {len(serializer.data)} orders")
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        """
        Accepts a payload like:
        {
            "customer_name": "Guest",
            "customer_email": "guest@example.com",
            "order_source": "manual",  # Optional: "user" or "manual"
            "order_items": [
                {"product_name": "Widget", "quantity": 2, "price": 20},
                {"product_name": "Gadget", "quantity": 1, "price": 25}
            ]
        }
        """
        logger.info(f"POST /api/core/user/orders/ - IP: {request.META.get('REMOTE_ADDR')}")
        logger.info(f"Request data: {request.data}")
        
        data = request.data
        customer_name = data.get("customer_name", "Guest")
        customer_email = data.get("customer_email", "")
        order_source = data.get("order_source", "user")  # Default to "user"
        order_items = data.get("order_items", [])

        if not order_items:
            logger.error("No order items provided in request")
            return Response({"error": "No order items provided"}, status=400)

        logger.info(f"Creating {len(order_items)} orders for customer: {customer_name}, source: {order_source}")
        created_orders = []
        
        for item in order_items:
            # Resolve tenant from authenticated user
            tenant = self._resolve_tenant(request)

            order_data = {
                "customer_name": customer_name,
                "product_name": item.get("product_name"),
                "quantity": item.get("quantity", 1),
                "total": item.get("quantity", 1) * item.get("price", 0),
                "status": "pending",
                "order_source": order_source
            }
            serializer = OrderSerializer(data=order_data, context={"request": request})
            if serializer.is_valid():
                order = serializer.save()
                if request.user and request.user.is_authenticated:
                    order.created_by = request.user
                    order.tenant = tenant
                    order.save(update_fields=['created_by', 'tenant'])
                created_orders.append(serializer.data)
                logger.info(f"Order created: {order.id} - {item.get('product_name')} - tenant: {tenant}")
            else:
                logger.error(f"Order validation failed: {serializer.errors}")
                return Response(serializer.errors, status=400)

        # Broadcast to WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "orders",
            {
                "type": "order_message",
                "message": created_orders,
            }
        )
        
        logger.info(f"Successfully created {len(created_orders)} orders and broadcasted to WebSocket")
        return Response(created_orders, status=201)

    @transaction.atomic
    def patch(self, request):
        """
        Update order status
        Accepts: {"id": 123, "status": "confirmed"}
        """
        logger.info(f"PATCH /api/core/orders/ - IP: {request.META.get('REMOTE_ADDR')}")
        logger.info(f"Request data: {request.data}")
        
        order_id = request.data.get("id")
        new_status = request.data.get("status")
        
        if not order_id or not new_status:
            logger.error("Missing id or status in request")
            return Response({"error": "Order ID and status are required"}, status=400)
        
        try:
            order = Order.objects.get(id=order_id)
            old_status = order.status
            order.status = new_status.lower()
            order.save()
            
            logger.info(f"Order {order_id} status updated: {old_status} -> {new_status}")
            
            # Broadcast status change via WebSocket
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "orders",
                {
                    "type": "order_message",
                    "message": {
                        "action": "status_update",
                        "order_id": order_id,
                        "status": new_status
                    },
                }
            )
            
            serializer = OrderSerializer(order)
            return Response({
                "message": "Order status updated successfully",
                "order": serializer.data
            })
            
        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found")
            return Response({"error": "Order not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            return Response({"error": str(e)}, status=500)


class BusinessSettingsView(APIView):
    """
    Handles business settings:
    - GET /api/business-settings/ - Get current business settings
    - POST /api/business-settings/ - Update business settings
    """
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info(f"GET /api/business-settings/ - IP: {request.META.get('REMOTE_ADDR')}")
        settings = BusinessSettings.get_settings()
        
        data = {
            'businessName': settings.business_name,
            'businessType': settings.business_type,
            'phone': settings.phone,
            'email': settings.email,
            'location': settings.location,
            'district': settings.district,
            'town': settings.town,
            'poBox': settings.po_box,
            'country': settings.country,
            'taxId': settings.tax_id,
            'registrationNumber': settings.registration_number,
            'website': settings.website,
        }
        
        logger.info(f"Returning business settings for: {settings.business_name}")
        return Response(data)

    def post(self, request):
        logger.info(f"POST /api/business-settings/ - IP: {request.META.get('REMOTE_ADDR')}")
        logger.info(f"Request data: {request.data}")
        
        data = request.data
        settings = BusinessSettings.get_settings()
        
        # Update fields
        settings.business_name = data.get('businessName', settings.business_name)
        settings.business_type = data.get('businessType', '')
        settings.phone = data.get('phone', settings.phone)
        settings.email = data.get('email', '')
        settings.location = data.get('location', settings.location)
        settings.district = data.get('district', settings.district)
        settings.town = data.get('town', settings.town)
        settings.po_box = data.get('poBox', '')
        settings.country = data.get('country', 'Uganda')
        settings.tax_id = data.get('taxId', '')
        settings.registration_number = data.get('registrationNumber', '')
        settings.website = data.get('website', '')
        
        settings.save()
        
        # Also update the current user's tenant BusinessConfig if business_type changed
        if 'businessType' in data and data['businessType']:
            try:
                # Get current user's tenant
                user = request.user
                tenant = getattr(user, 'tenant', None)
                if not tenant:
                    from tenants.models import TenantMembership
                    membership = TenantMembership.objects.filter(user=user).first()
                    tenant = membership.tenant if membership else None
                
                if tenant:
                    business_config, created = BusinessConfig.objects.get_or_create(
                        tenant=tenant,
                        defaults={'business_type': data['businessType']}
                    )
                    if not created and business_config.business_type != data['businessType']:
                        business_config.business_type = data['businessType']
                        business_config.save()
                        logger.info(f"Updated BusinessConfig business_type for tenant {tenant.name}")
            except Exception as e:
                logger.warning(f"Failed to update BusinessConfig business_type: {e}")
        
        logger.info(f"Business settings updated successfully for: {settings.business_name}")
        
        return Response({
            'message': 'Business settings updated successfully',
            'data': {
                'businessName': settings.business_name,
                'businessType': settings.business_type,
                'phone': settings.phone,
                'email': settings.email,
                'location': settings.location,
                'district': settings.district,
                'town': settings.town,
                'poBox': settings.po_box,
                'country': settings.country,
                'taxId': settings.tax_id,
                'registrationNumber': settings.registration_number,
                'website': settings.website,
            }
        })


class CustomerView(APIView):
    """
    Handles customer management:
    - GET /api/customers/ - Get all customers
    - POST /api/customers/ - Create or update customer
    """
    permission_classes = [AllowAny]

    def get(self, request):
        logger.info(f"GET /api/customers/ - IP: {request.META.get('REMOTE_ADDR')}")
        if request.user.is_superuser:
            customers = Customer.objects.all()
        else:
            tenant = getattr(request.user, 'tenant', None)
            if not tenant:
                from tenants.models import TenantMembership
                membership = TenantMembership.objects.filter(user=request.user).first()
                tenant = membership.tenant if membership else None
            if not tenant:
                return Response([])
            customers = Customer.objects.filter(tenant=tenant)
        data = [{
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email,
            'address': c.address,
            'totalDebt': float(c.total_debt),
            'createdAt': c.created_at.isoformat(),
            'updatedAt': c.updated_at.isoformat(),
        } for c in customers]
        logger.info(f"Returning {len(data)} customers")
        return Response(data)

    def post(self, request):
        logger.info(f"POST /api/customers/ - IP: {request.META.get('REMOTE_ADDR')}")
        data = request.data
        name = (data.get('name') or '').strip() or 'Walk-in Customer'
        phone = (data.get('phone') or '').strip() or '0000000000'
        email = (data.get('email') or '').strip()
        address = (data.get('address') or data.get('location') or '').strip()

        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            from tenants.models import TenantMembership
            membership = TenantMembership.objects.filter(user=request.user).first()
            tenant = membership.tenant if membership else None

        customer, _ = Customer.objects.update_or_create(
            phone=phone,
            defaults={
                'name': name,
                'email': email or '',
                'address': address or '',
                'tenant': tenant,
            }
        )
        
        logger.info(f"Customer created/updated: {customer.id} - {customer.name}")
        
        return Response({
            'message': 'Customer saved successfully',
            'data': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'email': customer.email,
                'address': customer.address,
                'totalDebt': float(customer.total_debt),
            }
        }, status=201)


class ReceiptView(APIView):
    """
    Handles receipt management:
    - GET /api/receipts/?receipt_number=XXX - Get receipt by receipt number
    - GET /api/receipts/ - Get all receipts
    - POST /api/receipts/ - Create new receipt
    """
    permission_classes = [IsAuthenticated]

    def _resolve_tenant(self, request):
        user = request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            tenant = Tenant.objects.filter(admin=user).first()
            if tenant:
                user.tenant = tenant
                user.save(update_fields=['tenant'])
        return tenant

    def _get_logo_url(self, tenant):
        """Fetch the Cloudinary logo URL for the tenant's theme."""
        if not tenant:
            return None
        try:
            from core.business_config import Theme
            theme = Theme.objects.get(tenant=tenant)
            if theme.logo:
                url = theme.logo.url
                return url if url else None
        except Exception:
            pass
        return None

    def get(self, request):
        logger.info(f"GET /api/receipts/ - IP: {request.META.get('REMOTE_ADDR')}")
        receipt_number = request.query_params.get('receipt_number')

        if request.user.is_superuser:
            tenant = None  # superuser sees all
        else:
            tenant = self._resolve_tenant(request)
            if not tenant:
                return Response([], status=status.HTTP_200_OK)

        if receipt_number:
            try:
                qs = Receipt.objects.filter(receipt_number=receipt_number)
                if tenant:
                    qs = qs.filter(tenant=tenant)
                receipt = qs.get()
                items = receipt.items.all()
                customer_email = ''
                customer_location = ''
                customer_record = None
                if receipt.customer_phone:
                    customer_record = Customer.objects.filter(phone=receipt.customer_phone).order_by('-updated_at').first()
                if not customer_record and receipt.customer_name:
                    customer_record = Customer.objects.filter(name=receipt.customer_name).order_by('-updated_at').first()
                if customer_record:
                    customer_email = customer_record.email or ''
                    customer_location = customer_record.address or ''
                data = {
                    'receiptNumber': receipt.receipt_number,
                    'customerName': receipt.customer_name,
                    'customerPhone': receipt.customer_phone,
                    'customerEmail': customer_email,
                    'customerLocation': customer_location,
                    'paymentMethod': receipt.payment_method,
                    'mobileMoneyNumber': receipt.mobile_money_number,
                    'subTotal': float(receipt.sub_total),
                    'taxAmount': float(receipt.tax_amount),
                    'totalAmount': float(receipt.total_amount),
                    'amountPaid': float(receipt.amount_paid),
                    'debtAmount': float(receipt.debt_amount),
                    'debtPartialPaymentMethod': receipt.debt_partial_payment_method,
                    'debtPartialMobileNumber': receipt.debt_partial_mobile_number,
                    'createdAt': receipt.created_at.isoformat(),
                    'logoUrl': self._get_logo_url(receipt.tenant),
                    'items': [{
                        'productName': item.product_name,
                        'quantity': item.quantity,
                        'priceType': item.price_type,
                        'unitPrice': float(item.unit_price),
                        'totalPrice': float(item.total_price),
                        'isDebt': item.is_debt,
                    } for item in items]
                }
                logger.info(f"Found receipt: {receipt_number}")
                return Response(data)
            except Receipt.DoesNotExist:
                logger.warning(f"Receipt not found: {receipt_number}")
                return Response({'error': 'Receipt not found'}, status=404)
        else:
            receipts = Receipt.objects.all().order_by('-created_at')
            if tenant:
                receipts = receipts.filter(tenant=tenant)
            receipts = receipts[:100]
            data = [{
                'receiptNumber': r.receipt_number,
                'customerName': r.customer_name or 'Walk-in',
                'totalAmount': float(r.total_amount),
                'amountPaid': float(r.amount_paid),
                'paymentMethod': r.payment_method,
                'createdAt': r.created_at.isoformat(),
            } for r in receipts]
            logger.info(f"Returning {len(data)} receipts")
            return Response(data)

    @transaction.atomic
    def post(self, request):
        logger.info(f"POST /api/receipts/ - IP: {request.META.get('REMOTE_ADDR')}")
        data = request.data

        tenant = self._resolve_tenant(request) if not request.user.is_superuser else None

        resolved_name = (data.get('customerName') or '').strip() or 'Walk-in Customer'
        resolved_phone = (data.get('customerPhone') or '').strip() or '0000000000'
        customer_email = (data.get('customerEmail') or '').strip()
        customer_location = (data.get('customerLocation') or data.get('customerAddress') or '').strip()

        receipt_number = Receipt.generate_receipt_number()

        receipt = Receipt.objects.create(
            tenant=tenant,
            receipt_number=receipt_number,
            customer_name=resolved_name,
            customer_phone=resolved_phone,
            payment_method=data.get('paymentMethod', 'cash'),
            mobile_money_number=data.get('mobileMoneyNumber', ''),
            sub_total=data.get('subTotal', 0),
            tax_amount=data.get('taxAmount', 0),
            total_amount=data.get('totalAmount', 0),
            amount_paid=data.get('amountPaid', 0),
            debt_amount=data.get('debtAmount', 0),
            debt_partial_payment_method=data.get('debtPartialPaymentMethod', ''),
            debt_partial_mobile_number=data.get('debtPartialMobileNumber', ''),
        )

        try:
            Customer.get_or_create_customer(
                name=resolved_name,
                phone=resolved_phone,
                email=customer_email,
                address=customer_location
            )
        except Exception as exc:
            logger.warning(f"Failed to sync customer for receipt {receipt_number}: {exc}")

        items_data = data.get('items', [])
        debt_product_ids = {str(pid) for pid in data.get('debtProductIds', [])}

        for item_data in items_data:
            item_identifier = str(item_data.get('id') or item_data.get('productId') or item_data.get('productName'))
            is_debt = bool(item_data.get('isDebt')) or item_identifier in debt_product_ids
            ReceiptItem.objects.create(
                receipt=receipt,
                product_name=item_data.get('productName'),
                quantity=item_data.get('quantity'),
                price_type=item_data.get('priceType'),
                unit_price=item_data.get('unitPrice'),
                total_price=item_data.get('totalPrice'),
                is_debt=is_debt,
            )

        logger.info(f"Receipt created: {receipt_number}")

        return Response({
            'message': 'Receipt created successfully',
            'receiptNumber': receipt_number,
            'data': {
                'receiptNumber': receipt.receipt_number,
                'customerName': receipt.customer_name,
                'customerEmail': customer_email,
                'customerLocation': customer_location,
                'totalAmount': float(receipt.total_amount),
                'createdAt': receipt.created_at.isoformat(),
                'logoUrl': self._get_logo_url(tenant),
            }
        }, status=201)


class AbandonedCartView(APIView):
    """
    Handles abandoned cart operations:
    - GET /api/core/abandoned-carts/ - List all abandoned carts
    - GET /api/core/abandoned-carts/?cart_source=user|admin_manual - Filter by source
    - GET /api/core/abandoned-carts/?recovered=true|false - Filter by recovery status
    - POST /api/core/abandoned-carts/ - Create/save an abandoned cart
    - PATCH /api/core/abandoned-carts/<id>/ - Mark as recovered or add notes
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        logger.info(f"GET /api/abandoned-carts/ - IP: {request.META.get('REMOTE_ADDR')}")
        cart_id = request.query_params.get('id')
        tenant_uuid = request.query_params.get('tenant_uuid')
        # Get specific cart by ID
        if cart_id:
            try:
                cart = AbandonedCart.objects.get(id=cart_id)
                # Enforce tenant filtering
                if not request.user.is_superuser and hasattr(request.user, 'tenant_id') and request.user.tenant_id:
                    if not cart.user or cart.user.tenant_id != request.user.tenant_id:
                        return Response({'error': 'Not found for this tenant'}, status=404)
                elif tenant_uuid:
                    from tenants.models import Tenant
                    try:
                        tenant = Tenant.objects.get(uuid=tenant_uuid)
                        if not cart.user or cart.user.tenant_id != tenant.id:
                            return Response({'error': 'Not found for this tenant'}, status=404)
                    except Tenant.DoesNotExist:
                        return Response({'error': 'Tenant not found for given uuid.'}, status=404)
                items = cart.items.all()
                data = {
                    'id': cart.id,
                    'cartSource': cart.cart_source,
                    'customerName': cart.customer_name,
                    'customerEmail': cart.customer_email,
                    'customerPhone': cart.customer_phone,
                    'totalAmount': float(cart.total_amount),
                    'itemCount': cart.item_count,
                    'createdAt': cart.created_at.isoformat(),
                    'lastUpdated': cart.last_updated.isoformat(),
                    'abandonedAt': cart.abandoned_at.isoformat() if cart.abandoned_at else None,
                    'recovered': cart.recovered,
                    'recoveredAt': cart.recovered_at.isoformat() if cart.recovered_at else None,
                    'notes': cart.notes,
                    'userName': cart.user.username if cart.user else None,
                    'items': [{
                        'id': item.id,
                        'productName': item.product_name,
                        'productId': item.product_id,
                        'quantity': item.quantity,
                        'priceType': item.price_type,
                        'unitPrice': float(item.unit_price),
                        'totalPrice': float(item.total_price),
                        'addedAt': item.added_at.isoformat(),
                    } for item in items]
                }
                logger.info(f"Returning cart {cart_id}")
                return Response(data)
            except AbandonedCart.DoesNotExist:
                return Response({'error': 'Cart not found'}, status=404)
        # List all carts with filters
        carts = AbandonedCart.objects.all().select_related('user')
        if not request.user.is_superuser and hasattr(request.user, 'tenant_id') and request.user.tenant_id:
            carts = carts.filter(user__tenant_id=request.user.tenant_id)
        elif tenant_uuid:
            from tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(uuid=tenant_uuid)
                carts = carts.filter(user__tenant_id=tenant.id)
            except Tenant.DoesNotExist:
                return Response({'error': 'Tenant not found for given uuid.'}, status=404)
        # Apply filters
        cart_source = request.query_params.get('cart_source')
        if cart_source:
            carts = carts.filter(cart_source=cart_source)
        recovered = request.query_params.get('recovered')
        if recovered is not None:
            is_recovered = recovered.lower() == 'true'
            carts = carts.filter(recovered=is_recovered)
        # Limit results
        limit = int(request.query_params.get('limit', 100))
        carts = carts[:limit]
        data = [{
            'id': cart.id,
            'cartSource': cart.cart_source,
            'customerName': cart.customer_name,
            'customerEmail': cart.customer_email,
            'customerPhone': cart.customer_phone,
            'totalAmount': float(cart.total_amount),
            'itemCount': cart.item_count,
            'createdAt': cart.created_at.isoformat(),
            'lastUpdated': cart.last_updated.isoformat(),
            'abandonedAt': cart.abandoned_at.isoformat() if cart.abandoned_at else None,
            'recovered': cart.recovered,
            'recoveredAt': cart.recovered_at.isoformat() if cart.recovered_at else None,
            'notes': cart.notes,
            'userName': cart.user.username if cart.user else None,
        } for cart in carts]
        logger.info(f"Returning {len(data)} abandoned carts")
        return Response(data)
    
    @transaction.atomic
    def post(self, request):
        logger.info(f"POST /api/abandoned-carts/ - IP: {request.META.get('REMOTE_ADDR')}")
        
        data = request.data
        session_id = data.get('session_id', '')
        cart_source = data.get('cart_source', 'user')
        
        # Check if cart already exists for this session and hasn't been recovered
        existing_cart = None
        if session_id and cart_source == 'user':
            try:
                existing_cart = AbandonedCart.objects.filter(
                    session_id=session_id,
                    cart_source='user',
                    recovered=False
                ).latest('last_updated')
            except AbandonedCart.DoesNotExist:
                pass
        
        if existing_cart:
            # Update existing cart
            cart = existing_cart
            cart.customer_name = data.get('customer_name', cart.customer_name)
            cart.customer_email = data.get('customer_email', cart.customer_email)
            cart.customer_phone = data.get('customer_phone', cart.customer_phone)
            cart.notes = data.get('notes', cart.notes)
            cart.last_updated = timezone.now()
            cart.abandoned_at = timezone.now()
            cart.save()
            
            # Delete old items and create new ones
            cart.items.all().delete()
            logger.info(f"Updating existing abandoned cart: {cart.id}")
        else:
            # Create new abandoned cart
            cart = AbandonedCart.objects.create(
                cart_source=cart_source,
                customer_name=data.get('customer_name', ''),
                customer_email=data.get('customer_email', ''),
                customer_phone=data.get('customer_phone', ''),
                session_id=session_id,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                notes=data.get('notes', ''),
                abandoned_at=timezone.now(),
            )
            logger.info(f"Creating new abandoned cart: {cart.id}")
        
        # Create cart items
        items_data = data.get('items', [])
        for item_data in items_data:
            AbandonedCartItem.objects.create(
                cart=cart,
                product_name=item_data.get('product_name'),
                product_id=item_data.get('product_id'),
                quantity=item_data.get('quantity'),
                price_type=item_data.get('price_type', 'retail'),
                unit_price=item_data.get('unit_price'),
                total_price=item_data.get('total_price', item_data.get('quantity', 0) * item_data.get('unit_price', 0)),
            )
        
        # Calculate totals
        cart.calculate_totals()
        
        logger.info(f"Abandoned cart saved: {cart.id} - {cart.item_count} items, Total: {cart.total_amount}")
        
        return Response({
            'message': 'Abandoned cart saved successfully',
            'cartId': cart.id,
            'data': {
                'id': cart.id,
                'cart_source': cart.cart_source,
                'total_amount': float(cart.total_amount),
                'item_count': cart.item_count,
                'created_at': cart.created_at.isoformat(),
            }
        }, status=201)
    
    @transaction.atomic
    def patch(self, request):
        logger.info(f"PATCH /api/abandoned-carts/ - IP: {request.META.get('REMOTE_ADDR')}")
        
        cart_id = request.data.get('id')
        if not cart_id:
            return Response({'error': 'Cart ID required'}, status=400)
        
        try:
            cart = AbandonedCart.objects.get(id=cart_id)
            
            # Update fields
            if 'recovered' in request.data:
                cart.recovered = request.data['recovered']
                if cart.recovered and not cart.recovered_at:
                    cart.recovered_at = timezone.now()
            
            if 'notes' in request.data:
                cart.notes = request.data['notes']
            
            if 'convertedOrderId' in request.data:
                try:
                    order = Order.objects.get(id=request.data['convertedOrderId'])
                    cart.converted_order = order
                    cart.recovered = True
                    cart.recovered_at = timezone.now()
                except Order.DoesNotExist:
                    pass
            
            cart.save()
            
            logger.info(f"Abandoned cart {cart_id} updated")
            
            return Response({
                'message': 'Cart updated successfully',
                'data': {
                    'id': cart.id,
                    'recovered': cart.recovered,
                    'recoveredAt': cart.recovered_at.isoformat() if cart.recovered_at else None,
                    'notes': cart.notes,
                }
            })
            
        except AbandonedCart.DoesNotExist:
            return Response({'error': 'Cart not found'}, status=404)


class AppointmentView(APIView):
    """CRUD for appointments/scheduling with optional reminders."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List appointments with optional filters: status, upcoming=true, limit, mine, assignedTo."""
        status_param = request.query_params.get('status')
        upcoming = request.query_params.get('upcoming')
        limit = int(request.query_params.get('limit', 100))
        mine = request.query_params.get('mine')
        assignee = request.query_params.get('assignedTo') or request.query_params.get('assignee')
        created_by = request.query_params.get('createdBy')
        tenant_uuid = request.query_params.get('tenant_uuid')
        qs = Appointment.objects.all().order_by('start_time')
        # Enforce tenant filtering
        if not request.user.is_superuser and hasattr(request.user, 'tenant_id') and request.user.tenant_id:
            qs = qs.filter(created_by__tenant_id=request.user.tenant_id)
        elif tenant_uuid:
            from tenants.models import Tenant
            try:
                tenant = Tenant.objects.get(uuid=tenant_uuid)
                qs = qs.filter(created_by__tenant_id=tenant.id)
            except Tenant.DoesNotExist:
                return Response({'error': 'Tenant not found for given uuid.'}, status=404)
        if status_param:
            qs = qs.filter(status=status_param)
        if upcoming is not None:
            try:
                is_upcoming = upcoming.lower() == 'true'
                if is_upcoming:
                    qs = qs.filter(start_time__gte=timezone.now())
            except Exception:
                pass
        if mine and mine.lower() == 'true' and request.user.is_authenticated:
            qs = qs.filter(Q(assigned_to=request.user) | Q(created_by=request.user) | Q(assigned_to__isnull=True))
        if assignee:
            qs = qs.filter(assigned_to_id=assignee)
        if getattr(request.user, 'role', None) == ROLE_WORKER:
            qs = qs.filter(Q(assigned_to=request.user) | Q(created_by=request.user) | Q(assigned_to__isnull=True))
        if created_by:
            qs = qs.filter(created_by_id=created_by)
        qs = qs[:limit]
        data = [self._serialize(appt) for appt in qs]
        return Response(data)

    def post(self, request):
        """Create a new appointment (assign to self or another worker)."""
        payload = request.data or {}

        try:
            start_time = payload.get('startTime') or payload.get('start_time')
            end_time = payload.get('endTime') or payload.get('end_time')

            if not start_time:
                return Response({'error': 'startTime is required'}, status=400)

            start_dt = timezone.make_aware(timezone.datetime.fromisoformat(start_time.replace('Z', '+00:00')))
            end_dt = None
            if end_time:
                end_dt = timezone.make_aware(timezone.datetime.fromisoformat(end_time.replace('Z', '+00:00')))

            assigned_to_id = payload.get('assignedTo') or payload.get('assigned_to')
            assigned_user = None
            if assigned_to_id:
                assigned_user = User.objects.filter(id=assigned_to_id).first()

            appt = Appointment.objects.create(
                title=payload.get('title') or 'Appointment',
                participant=payload.get('participant', ''),
                location=payload.get('location', ''),
                notes=payload.get('notes', ''),
                start_time=start_dt,
                end_time=end_dt,
                is_all_day=bool(payload.get('isAllDay', False)),
                status=payload.get('status', 'upcoming'),
                reminder_minutes_before=int(payload.get('reminderMinutes', payload.get('reminder_minutes_before', 30) or 30)),
                recurrence=payload.get('recurrence', 'none'),
                recurrence_until=payload.get('recurrenceUntil'),
                recurrence_count=payload.get('recurrenceCount'),
                created_by=request.user if request.user.is_authenticated else None,
                assigned_to=assigned_user if assigned_user else (request.user if request.user.is_authenticated else None),
            )

            attendees_payload = payload.get('attendees', []) or []
            for attendee in attendees_payload:
                email = attendee.get('email')
                if not email:
                    continue
                AppointmentAttendee.objects.create(
                    appointment=appt,
                    email=email,
                    name=attendee.get('name', ''),
                    status=attendee.get('status', 'invited'),
                    user=User.objects.filter(id=attendee.get('userId')).first() if attendee.get('userId') else None,
                )

            return Response(self._serialize(appt), status=201)
        except Exception as exc:
            logger.error(f"Failed to create appointment: {exc}")
            return Response({'error': str(exc)}, status=400)

    def patch(self, request):
        """Update status or basic fields of an appointment."""
        appt_id = request.data.get('id')
        if not appt_id:
            return Response({'error': 'id is required'}, status=400)

        try:
            appt = Appointment.objects.get(id=appt_id)
        except Appointment.DoesNotExist:
            return Response({'error': 'Appointment not found'}, status=404)

        for field, key in [
            ('title', 'title'),
            ('participant', 'participant'),
            ('location', 'location'),
            ('notes', 'notes'),
            ('status', 'status'),
        ]:
            if key in request.data:
                setattr(appt, field, request.data.get(key))

        if 'isAllDay' in request.data:
            appt.is_all_day = bool(request.data.get('isAllDay'))

        if 'startTime' in request.data or 'start_time' in request.data:
            start_time = request.data.get('startTime') or request.data.get('start_time')
            appt.start_time = timezone.make_aware(timezone.datetime.fromisoformat(start_time.replace('Z', '+00:00')))

        if 'endTime' in request.data or 'end_time' in request.data:
            end_time = request.data.get('endTime') or request.data.get('end_time')
            if end_time:
                appt.end_time = timezone.make_aware(timezone.datetime.fromisoformat(end_time.replace('Z', '+00:00')))
            else:
                appt.end_time = None

        if 'reminderMinutes' in request.data or 'reminder_minutes_before' in request.data:
            appt.reminder_minutes_before = int(request.data.get('reminderMinutes', request.data.get('reminder_minutes_before')))

        if 'reminderSent' in request.data:
            appt.reminder_sent = bool(request.data.get('reminderSent'))

        if 'recurrence' in request.data:
            appt.recurrence = request.data.get('recurrence') or 'none'

        if 'recurrenceUntil' in request.data:
            appt.recurrence_until = request.data.get('recurrenceUntil') or None

        if 'recurrenceCount' in request.data:
            appt.recurrence_count = request.data.get('recurrenceCount') or None

        if 'assignedTo' in request.data or 'assigned_to' in request.data:
            assigned_to_id = request.data.get('assignedTo', request.data.get('assigned_to'))
            appt.assigned_to = User.objects.filter(id=assigned_to_id).first() if assigned_to_id else None

        if 'attendees' in request.data:
            attendees_payload = request.data.get('attendees') or []
            appt.attendees.all().delete()
            for attendee in attendees_payload:
                email = attendee.get('email')
                if not email:
                    continue
                AppointmentAttendee.objects.create(
                    appointment=appt,
                    email=email,
                    name=attendee.get('name', ''),
                    status=attendee.get('status', 'invited'),
                    user=User.objects.filter(id=attendee.get('userId')).first() if attendee.get('userId') else None,
                )

        appt.save()
        return Response(self._serialize(appt))

    def _serialize(self, appt: Appointment):
        return {
          'id': appt.id,
          'title': appt.title,
          'participant': appt.participant,
          'location': appt.location,
          'notes': appt.notes,
          'startTime': appt.start_time.isoformat(),
          'endTime': appt.end_time.isoformat() if appt.end_time else None,
          'status': appt.status,
          'reminderMinutes': appt.reminder_minutes_before,
          'reminderSent': appt.reminder_sent,
          'recurrence': appt.recurrence,
          'recurrenceUntil': appt.recurrence_until.isoformat() if appt.recurrence_until else None,
          'recurrenceCount': appt.recurrence_count,
          'isAllDay': appt.is_all_day,
          'assignedTo': self._user_payload(appt.assigned_to),
          'createdBy': self._user_payload(appt.created_by),
          'attendees': [self._attendee_payload(a) for a in appt.attendees.all()],
          'createdAt': appt.created_at.isoformat(),
          'updatedAt': appt.updated_at.isoformat(),
        }

    def _user_payload(self, user):
        if not user:
            return None
        return {
            'id': user.id,
            'name': user.get_full_name() or user.username,
            'email': user.email,
            'role': getattr(user, 'role', None),
        }

    def _attendee_payload(self, attendee: AppointmentAttendee):
        return {
            'id': attendee.id,
            'name': attendee.name,
            'email': attendee.email,
            'status': attendee.status,
            'userId': attendee.user_id,
        }


class WorkerListView(APIView):
    """Return workers/admins in the same tenant for assignment."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = User.objects.filter(role__in=[ROLE_WORKER, ROLE_TENANT_ADMIN, ROLE_SUPERADMIN])
        tenant_uuid = request.query_params.get('tenant_uuid')
        if tenant_uuid:
            try:
                tenant = Tenant.objects.get(uuid=tenant_uuid)
                qs = qs.filter(tenant_id=tenant.id)
            except Tenant.DoesNotExist:
                return Response({'error': 'Tenant not found for given uuid.'}, status=status.HTTP_404_NOT_FOUND)
        elif getattr(request.user, 'tenant_id', None):
            qs = qs.filter(tenant_id=request.user.tenant_id)

        data = [
            {
                'id': user.id,
                'name': user.get_full_name() or user.username,
                'email': user.email,
                'role': user.role,
            }
            for user in qs.order_by('username')
        ]
        return Response(data)

