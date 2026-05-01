from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Plan, TenantSubscription
from .serializers import PlanSerializer, SubscriptionSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def list_plans(request):
    """Return all active plans — public endpoint used by Pricing page."""
    plans = Plan.objects.filter(is_active=True).order_by('price_ugx')
    return Response(PlanSerializer(plans, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    """Return the current tenant's subscription, auto-syncing trial expiry."""
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found for this user.'}, status=status.HTTP_404_NOT_FOUND)

    sub = getattr(tenant, 'subscription', None)

    # Auto-create a free trial subscription if none exists
    if not sub:
        free_plan = Plan.objects.filter(key='free').first()
        if not free_plan:
            return Response({'error': 'Free plan not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        trial_start = timezone.now()
        trial_end = trial_start + timedelta(days=free_plan.trial_days or 14)
        sub = TenantSubscription.objects.create(
            tenant=tenant,
            plan=free_plan,
            status=TenantSubscription.STATUS_TRIAL,
            trial_start=trial_start,
            trial_end=trial_end,
        )

    sub.sync_status()
    return Response(SubscriptionSerializer(sub).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def select_plan(request):
    """
    Select or upgrade a plan.
    Body: { "plan_key": "starter" | "business" | "enterprise" }
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found.'}, status=status.HTTP_404_NOT_FOUND)

    plan_key = request.data.get('plan_key')
    if not plan_key:
        return Response({'error': 'plan_key is required.'}, status=status.HTTP_400_BAD_REQUEST)

    plan = Plan.objects.filter(key=plan_key, is_active=True).first()
    if not plan:
        return Response({'error': f'Plan "{plan_key}" not found.'}, status=status.HTTP_404_NOT_FOUND)

    sub, created = TenantSubscription.objects.get_or_create(
        tenant=tenant,
        defaults={
            'plan': plan,
            'status': TenantSubscription.STATUS_TRIAL if plan.trial_days else TenantSubscription.STATUS_ACTIVE,
            'trial_start': timezone.now() if plan.trial_days else None,
            'trial_end': timezone.now() + timedelta(days=plan.trial_days) if plan.trial_days else None,
        }
    )

    if not created:
        # Upgrade/change plan
        sub.plan = plan
        sub.status = TenantSubscription.STATUS_ACTIVE
        sub.trial_start = None
        sub.trial_end = None
        sub.save(update_fields=['plan', 'status', 'trial_start', 'trial_end', 'updated_at'])

    return Response(SubscriptionSerializer(sub).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_product_limit(request):
    """Check if the tenant can add more products."""
    from product.models import Product

    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'can_add': False, 'reason': 'No tenant'})

    sub = getattr(tenant, 'subscription', None)
    if not sub:
        # Default: free trial limits
        count = Product.objects.filter(tenant=tenant).count()
        return Response({'can_add': count < 7, 'current': count, 'limit': 7, 'plan': 'free'})

    sub.sync_status()

    if sub.status == TenantSubscription.STATUS_EXPIRED:
        return Response({'can_add': False, 'reason': 'trial_expired', 'plan': sub.plan.key})

    limit = sub.plan.product_limit
    if limit == -1:
        return Response({'can_add': True, 'limit': -1, 'plan': sub.plan.key})

    count = Product.objects.filter(tenant=tenant).count()
    return Response({
        'can_add': count < limit,
        'current': count,
        'limit': limit,
        'plan': sub.plan.key,
        'days_left': sub.days_left,
    })
