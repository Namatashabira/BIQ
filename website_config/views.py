
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import Tenant, OrderSyncConfig, Order, AllowedOrigin
from .serializers import OrderSyncConfigSerializer, OrderSerializer, IncomingOrderSerializer, AllowedOriginSerializer
from rest_framework import generics

# List/Create allowed origins for the current tenant
class AllowedOriginListCreateView(generics.ListCreateAPIView):
	serializer_class = AllowedOriginSerializer
	permission_classes = [permissions.IsAuthenticated]

	def get_queryset(self):
		return AllowedOrigin.objects.filter(tenant=self.request.user.tenant)

	def perform_create(self, serializer):
		serializer.save(tenant=self.request.user.tenant)

# Delete a specific allowed origin
class AllowedOriginDeleteView(generics.DestroyAPIView):
	serializer_class = AllowedOriginSerializer
	permission_classes = [permissions.IsAuthenticated]
	lookup_url_kwarg = 'pk'

	def get_queryset(self):
		return AllowedOrigin.objects.filter(tenant=self.request.user.tenant)
from django.shortcuts import get_object_or_404

def get_tenant_by_api_key(api_key):
	return get_object_or_404(Tenant, api_key=api_key)

class OrderSyncConfigView(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def get(self, request):
		tenant = request.user.tenant  # Assumes user is linked to tenant
		config, _ = OrderSyncConfig.objects.get_or_create(tenant=tenant)
		return Response(OrderSyncConfigSerializer(config).data)

	def post(self, request):
		tenant = request.user.tenant
		config, _ = OrderSyncConfig.objects.get_or_create(tenant=tenant)
		serializer = OrderSyncConfigSerializer(config, data=request.data, partial=True)
		if serializer.is_valid():
			serializer.save()
			return Response(serializer.data)
		return Response(serializer.errors, status=400)

class IncomingOrderView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		serializer = IncomingOrderSerializer(data=request.data)
		if not serializer.is_valid():
			return Response({'error': 'Invalid payload', 'details': serializer.errors}, status=400)
		api_key = serializer.validated_data['api_key']
		payload = serializer.validated_data['payload']
		tenant = get_tenant_by_api_key(api_key)
		config = getattr(tenant, 'order_sync_config', None)
		if not config or not config.enabled:
			return Response({'error': 'Order sync not enabled for this tenant.'}, status=403)
		mapping = config.field_mapping or {}
		# Map fields
		try:
			order_data = {
				'customer_name': payload.get(mapping.get('customer_name', 'customer_name'), ''),
				'email': payload.get(mapping.get('email', 'email'), ''),
				'product_id': payload.get(mapping.get('product_id', 'product_id'), ''),
				'quantity': payload.get(mapping.get('quantity', 'quantity'), 1),
				'order_total': payload.get(mapping.get('order_total', 'order_total'), 0),
				'raw_payload': payload,
				'tenant': tenant,
			}
			# Validate required fields
			missing = [f for f in ['customer_name', 'email', 'product_id', 'order_total'] if not order_data[f]]
			if missing:
				raise ValueError(f"Missing required fields: {', '.join(missing)}")
			order = Order.objects.create(**order_data)
			return Response({'success': True, 'order': OrderSerializer(order).data})
		except Exception as e:
			order = Order.objects.create(
				tenant=tenant,
				customer_name=order_data.get('customer_name', ''),
				email=order_data.get('email', ''),
				product_id=order_data.get('product_id', ''),
				quantity=order_data.get('quantity', 1),
				order_total=order_data.get('order_total', 0),
				raw_payload=payload,
				status='error',
				error_message=str(e)
			)
			return Response({'error': str(e), 'order': OrderSerializer(order).data}, status=400)

class OrderSyncTestView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		api_key = request.data.get('api_key')
		payload = request.data.get('payload', {})
		tenant = get_tenant_by_api_key(api_key)
		config = getattr(tenant, 'order_sync_config', None)
		if not config or not config.enabled:
			return Response({'error': 'Order sync not enabled for this tenant.'}, status=403)
		mapping = config.field_mapping or {}
		# Simulate mapping
		mapped = {f: payload.get(mapping.get(f, f), None) for f in ['customer_name', 'email', 'product_id', 'quantity', 'order_total']}
		return Response({'success': True, 'mapped': mapped})

class OrderLogsView(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def get(self, request):
		tenant = request.user.tenant
		orders = Order.objects.filter(tenant=tenant).order_by('-created_at')[:10]
		return Response(OrderSerializer(orders, many=True).data)
