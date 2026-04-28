from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import CustomerReview
from .serializers import CustomerReviewSerializer
from django.db import models
from tenants.models import TenantMembership


def _get_tenant(user):
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        membership = TenantMembership.objects.filter(user=user).first()
        tenant = membership.tenant if membership else None
    return tenant


class CustomerReviewViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    serializer_class = CustomerReviewSerializer

    def get_queryset(self):
        tenant = _get_tenant(self.request.user)
        if not tenant:
            return CustomerReview.objects.none()
        return CustomerReview.objects.filter(tenant=tenant).order_by('-created_at')

    @action(detail=False, methods=['get'], url_path='product-reviews', permission_classes=[AllowAny])
    def product_reviews(self, request):
        """
        Returns all reviews and average rating for a given product_id.
        Query param: product_id
        """
        product_id = request.query_params.get('product_id')
        if not product_id:
            return Response({'detail': 'product_id required'}, status=400)
        # Scope by tenant if authenticated, otherwise return nothing
        tenant = _get_tenant(request.user) if request.user.is_authenticated else None
        qs = CustomerReview.objects.filter(product_id=product_id)
        if tenant:
            qs = qs.filter(tenant=tenant)
        else:
            qs = qs.none()
        qs = qs.order_by('-created_at')
        serializer = self.get_serializer(qs, many=True)
        avg_rating = qs.aggregate(avg=models.Avg('rating'))['avg']
        return Response({
            'reviews': serializer.data,
            'average_rating': avg_rating or 0,
            'count': qs.count(),
        })

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['user_ip'] = request.META.get('REMOTE_ADDR')
        if 'reviewer_name' not in data:
            data['reviewer_name'] = ""
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        tenant = _get_tenant(request.user)
        serializer.save(tenant=tenant)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'])
    def dashboard_reviews(self, request):
        product_id = request.query_params.get('product_id')
        qs = self.get_queryset()  # already tenant-scoped
        if product_id:
            qs = qs.filter(product_id=product_id)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
