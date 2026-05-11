from django.utils import timezone
from datetime import timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import Plan, TenantSubscription, PaymentRequest
from .serializers import PlanSerializer, SubscriptionSerializer, PaymentRequestSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def list_plans(request):
    plans = Plan.objects.filter(is_active=True).order_by('price_ugx')
    return Response(PlanSerializer(plans, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_subscription(request):
    # Superadmin is the owner — always has full unlimited access
    if request.user.is_superuser or getattr(request.user, 'role', None) == 'superadmin':
        return Response({
            'plan': {'key': 'enterprise', 'name': 'Owner', 'product_limit': -1, 'trial_days': 0, 'allowed_pages': []},
            'status': 'active',
            'is_trial_expired': False,
            'days_left': None,
            'trial_start': None,
            'trial_end': None,
        })

    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found for this user.'}, status=status.HTTP_404_NOT_FOUND)

    sub = getattr(tenant, 'subscription', None)

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
        sub.plan = plan
        sub.status = TenantSubscription.STATUS_ACTIVE
        sub.trial_start = None
        sub.trial_end = None
        sub.save(update_fields=['plan', 'status', 'trial_start', 'trial_end', 'updated_at'])

    return Response(SubscriptionSerializer(sub).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_product_limit(request):
    from product.models import Product

    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'can_add': False, 'reason': 'No tenant'})

    sub = getattr(tenant, 'subscription', None)
    if not sub:
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


# ── Payment Request (user submits payment proof) ──────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def payment_profile(request):
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found.'}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'GET':
        pr = PaymentRequest.objects.filter(tenant=tenant).order_by('-created_at').first()
        if pr:
            return Response({'sender_name': pr.sender_name, 'phone_number': pr.phone_number})
        return Response({'sender_name': '', 'phone_number': ''})
    sender_name  = request.data.get('sender_name', '').strip()
    phone_number = request.data.get('phone_number', '').strip()
    PaymentRequest.objects.filter(tenant=tenant, code_used=False).update(
        sender_name=sender_name, phone_number=phone_number
    )
    return Response({'sender_name': sender_name, 'phone_number': phone_number})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_payment_request(request):
    """
    User submits payment details.
    Body: { plan_key, sender_name, phone_number, payment_method, transaction_id }
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found.'}, status=status.HTTP_404_NOT_FOUND)

    plan_key = request.data.get('plan_key')
    plan = Plan.objects.filter(key=plan_key, is_active=True).first()
    if not plan:
        return Response({'error': 'Invalid plan.'}, status=status.HTTP_400_BAD_REQUEST)

    sender_name = request.data.get('sender_name', '').strip()
    phone_number = request.data.get('phone_number', '').strip()
    payment_method = request.data.get('payment_method', '').strip()
    transaction_id = request.data.get('transaction_id', '').strip()

    if not all([sender_name, phone_number, payment_method, transaction_id]):
        return Response({'error': 'All fields are required.'}, status=status.HTTP_400_BAD_REQUEST)

    # Prevent duplicate pending requests for same transaction
    if PaymentRequest.objects.filter(transaction_id=transaction_id, status=PaymentRequest.STATUS_PENDING).exists():
        return Response({'error': 'A request with this transaction ID is already pending.'}, status=status.HTTP_400_BAD_REQUEST)

    pr = PaymentRequest.objects.create(
        tenant=tenant,
        plan=plan,
        sender_name=sender_name,
        phone_number=phone_number,
        payment_method=payment_method,
        transaction_id=transaction_id,
    )

    return Response({
        'id': pr.id,
        'message': 'Payment request submitted. You will receive an activation code once verified.',
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def activate_plan(request):
    """
    User enters activation code to unlock their plan.
    Body: { activation_code }
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant found.'}, status=status.HTTP_404_NOT_FOUND)

    code = request.data.get('activation_code', '').strip().upper()
    if not code:
        return Response({'error': 'Activation code is required.'}, status=status.HTTP_400_BAD_REQUEST)

    pr = PaymentRequest.objects.filter(
        tenant=tenant,
        activation_code=code,
        status=PaymentRequest.STATUS_APPROVED,
        code_used=False,
    ).first()

    if not pr:
        return Response({'error': 'Invalid or already used activation code.'}, status=status.HTTP_400_BAD_REQUEST)

    # Check expiry
    if pr.code_expires_at and timezone.now() > pr.code_expires_at:
        return Response({'error': 'This activation code has expired. Please contact support.'}, status=status.HTTP_400_BAD_REQUEST)

    # Activate the plan
    sub, created = TenantSubscription.objects.get_or_create(
        tenant=tenant,
        defaults={'plan': pr.plan, 'status': TenantSubscription.STATUS_ACTIVE}
    )
    if not created:
        sub.plan = pr.plan
        sub.status = TenantSubscription.STATUS_ACTIVE
        sub.trial_start = None
        sub.trial_end = None
        sub.save(update_fields=['plan', 'status', 'trial_start', 'trial_end', 'updated_at'])

    pr.code_used = True
    pr.save(update_fields=['code_used', 'updated_at'])

    return Response({
        'message': f'Plan activated successfully! Welcome to {pr.plan.name}.',
        'plan': pr.plan.key,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def poll_activation_code(request):
    """
    User polls this endpoint after submitting payment.
    Returns the activation code once admin has approved it.
    """
    tenant = getattr(request.user, 'tenant', None)
    if not tenant:
        return Response({'status': 'no_tenant'}, status=status.HTTP_404_NOT_FOUND)

    pr = PaymentRequest.objects.filter(
        tenant=tenant,
        code_used=False,
    ).order_by('-created_at').first()

    if not pr:
        return Response({'status': 'not_found'})

    if pr.status == PaymentRequest.STATUS_PENDING:
        return Response({'status': 'pending'})

    if pr.status == PaymentRequest.STATUS_REJECTED:
        return Response({'status': 'rejected'})

    if pr.status == PaymentRequest.STATUS_APPROVED and pr.activation_code:
        # Check expiry
        if pr.code_expires_at and timezone.now() > pr.code_expires_at:
            return Response({'status': 'expired'})
        return Response({
            'status': 'approved',
            'activation_code': pr.activation_code,
            'code_expires_at': pr.code_expires_at,
            'plan_name': pr.plan.name,
        })

    return Response({'status': 'pending'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_payment_requests(request):
    """Super admin: list all payment requests."""
    if not (request.user.is_staff or request.user.is_superuser):
        return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    qs = PaymentRequest.objects.select_related('tenant', 'plan').all()
    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)

    return Response(PaymentRequestSerializer(qs, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_generate_code(request, pk):
    """Super admin: approve a payment request and generate activation code."""
    if not (request.user.is_staff or request.user.is_superuser):
        return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    pr = PaymentRequest.objects.filter(pk=pk).first()
    if not pr:
        return Response({'error': 'Payment request not found.'}, status=status.HTTP_404_NOT_FOUND)

    if pr.status == PaymentRequest.STATUS_APPROVED and pr.activation_code:
        return Response({'activation_code': pr.activation_code, 'already_generated': True})

    code = pr.generate_code()
    return Response({'activation_code': code, 'request_id': pr.id})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reject_request(request, pk):
    """Super admin: reject a payment request."""
    if not (request.user.is_staff or request.user.is_superuser):
        return Response({'error': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    pr = PaymentRequest.objects.filter(pk=pk).first()
    if not pr:
        return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    pr.status = PaymentRequest.STATUS_REJECTED
    pr.admin_note = request.data.get('note', '')
    pr.save(update_fields=['status', 'admin_note', 'updated_at'])
    return Response({'message': 'Request rejected.'})
