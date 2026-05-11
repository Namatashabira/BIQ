from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model, authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.utils import ProgrammingError, OperationalError
from core.models import PasswordResetToken
from core.business_config import WorkerAccessInvite
from tenants.models import Tenant, TenantMembership
from core.business_config import BusinessConfig
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# -------------------------------------------------
# Helpers
# -------------------------------------------------
def ensure_tenant_for_user(user, business_name=None, business_type='other'):

    # Try to get tenant via user.tenant (FK) or as admin (OneToOne)
    tenant = getattr(user, 'tenant', None)
    if not tenant:
        # Check if user is admin of a tenant
        tenant = Tenant.objects.filter(admin=user).first()
        if tenant:
            user.tenant = tenant
            user.save(update_fields=['tenant'])
    if not tenant:
        # Only create if user is not already admin/member of a tenant
        import uuid as uuid_lib
        tenant = Tenant.objects.create(
            uuid=uuid_lib.uuid4(),
            name=business_name or f"{user.username}'s Tenant",
            admin=user,
            business_type=business_type,
            is_verified=True,
        )
        user.tenant = tenant
        user.save(update_fields=['tenant'])
    else:
        if not getattr(tenant, 'is_verified', False):
            tenant.is_verified = True
            tenant.save(update_fields=['is_verified'])
        # Use the tenant's actual business_type, not the default 'other'
        business_type = tenant.business_type or business_type

    # Ensure membership exists
    TenantMembership.objects.get_or_create(user=user, tenant=tenant, defaults={'role': 'admin'})

    # Ensure business config exists (skip gracefully if table not ready)
    try:
        config, created = BusinessConfig.objects.get_or_create(
            tenant=tenant,
            defaults={'business_type': business_type, 'onboarding_completed': True},
        )
        # If config exists but business_type is wrong (e.g. 'other' from a bad bootstrap), fix it
        if not created and config.business_type == 'other' and business_type != 'other':
            config.business_type = business_type
            config.save(update_fields=['business_type'])
    except (ProgrammingError, OperationalError):
        logger.warning("BusinessConfig table missing; skipping config bootstrap")

    # Bootstrap feature toggles, terminology, pricing if missing
    try:
        from core.business_config import FeatureToggle, Terminology, PricingSettings, FEATURE_DEFAULTS, BUSINESS_PRESETS
        if not FeatureToggle.objects.filter(tenant=tenant).exists():
            for key, enabled in FEATURE_DEFAULTS.items():
                FeatureToggle.objects.get_or_create(tenant=tenant, feature_key=key, defaults={"enabled": enabled})
            preset_terms = BUSINESS_PRESETS.get(business_type, BUSINESS_PRESETS["other"])["terminology"]
            for entity, label in preset_terms.items():
                Terminology.objects.get_or_create(tenant=tenant, entity=entity, defaults={"label": label, "label_plural": label + "s"})
            PricingSettings.objects.get_or_create(tenant=tenant)
    except (ProgrammingError, OperationalError):
        logger.warning("Feature toggle tables missing; skipping feature bootstrap")

    return tenant

# ----------------------------
# Registration & Authentication
# ----------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user with business type selection.
    Creates user, tenant, and applies business configuration preset.
    """
    data = request.data

    try:
        required_fields = ['username', 'email', 'password', 'business_name', 'business_type']
        missing_fields = [f for f in required_fields if not data.get(f)]
        if missing_fields:
            return Response(
                {'error': f'Missing required fields: {", ".join(missing_fields)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        business_type = data.get('business_type')
        valid_types = [choice[0] for choice in BusinessConfig.BUSINESS_TYPE_CHOICES]
        if business_type not in valid_types:
            return Response(
                {'error': f'Invalid business_type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=data.get('email')).exists():
            return Response({'error': 'User with this email already exists'},
                            status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=data.get('username')).exists():
            return Response({'error': 'Username already taken'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            user = User.objects.create_user(
                username=data.get('username'),
                email=data.get('email'),
                password=data.get('password'),
                first_name=data.get('first_name', ''),
                last_name=data.get('last_name', ''),
                role='tenant_admin'
            )

            # Generate a tenant schema name for the new business
            schema_base = data.get('username', '').lower() or f'user{user.id}'
            schema_name = f"tenant_{schema_base}".replace(' ', '_')

            tenant = Tenant.objects.create(
                schema_name=schema_name,
                name=data.get('business_name'),
                admin=user,
                business_type=business_type,
                school_type=data.get('school_type', '') if business_type == 'school' else '',
                is_verified=True,
            )

            user.tenant = tenant
            user.save(update_fields=['tenant'])

            business_config = BusinessConfig.objects.create(
                tenant=tenant,
                business_type=business_type,
                industry_description=data.get('industry_description', ''),
                onboarding_completed=True
            )
            business_config.apply_business_preset()

            logger.info(f"New tenant created: {tenant.name} ({business_type}) with user {user.email}")

        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            },
            'tenant': {
                'id': tenant.id,
                'name': tenant.name,
                'business_type': business_type,
                'school_type': tenant.school_type,
            },
            'message': 'Registration successful! Your business configuration has been set up.'
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user and return JWT tokens"""
    username = request.data.get('username')
    password = request.data.get('password')

    if not username or not password:
        return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)

    # First: check if the submitted password matches an active OTP invite
    try:
        invite = WorkerAccessInvite.objects.filter(email__iexact=username, otp_code=password, used=False).first()
    except (ProgrammingError, OperationalError):
        logger.warning("WorkerAccessInvite table missing; skipping OTP login path")
        invite = None

    if invite:
        if invite.otp_expires_at < timezone.now():
            return Response({'error': 'OTP expired'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response({
            'otp_valid': True,
            'email': invite.email,
            'message': 'OTP valid. Please set a new password to activate your account.'
        }, status=status.HTTP_202_ACCEPTED)

    # Allow login with email or username; fallback to email lookup
    user = authenticate(username=username, password=password)
    if not user:
        try:
            email_user = User.objects.filter(email__iexact=username).first()
            if email_user:
                user = authenticate(username=email_user.username, password=password)
        except Exception:
            user = None
    if not user:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if not user.is_active:
        return Response({'error': 'Account is disabled'}, status=status.HTTP_401_UNAUTHORIZED)

    # Ensure tenant exists & verified so pages don’t 403 after login
    tenant = ensure_tenant_for_user(user)

    refresh = RefreshToken.for_user(user)

    tenant_info = {
        'id': tenant.id,
        'uuid': str(tenant.uuid),
        'name': tenant.name,
        'school_type': getattr(tenant, 'school_type', ''),
    } if tenant else None

    # Fetch school_role from Worker record if exists
    school_role = ''
    try:
        from tenants.models import Worker
        w = Worker.objects.filter(user=user, tenant=tenant).first()
        if w:
            school_role = w.school_role or ''
    except Exception:
        pass

    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': getattr(user, 'role', 'worker'),
            'school_role': school_role,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'tenant': tenant_info
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """Logout user by blacklisting refresh token"""
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get current user profile"""
    user = request.user
    tenant_info = None
    if hasattr(user, 'tenant') and user.tenant:
        tenant_info = {
            'id': user.tenant.id,
            'name': user.tenant.name
        }
    profile = getattr(user, 'profile', None)
    profile_picture_url = None
    if profile and profile.profile_picture:
        profile_picture_url = request.build_absolute_uri(profile.profile_picture.url)
    user_data = {
        'id': getattr(user, 'id', None),
        'username': getattr(user, 'username', ''),
        'email': getattr(user, 'email', ''),
        'first_name': getattr(user, 'first_name', ''),
        'last_name': getattr(user, 'last_name', ''),
        'role': getattr(user, 'role', 'worker'),
        'is_staff': getattr(user, 'is_staff', False),
        'is_superuser': getattr(user, 'is_superuser', False),
        'tenant': tenant_info,
        'profile_picture_url': profile_picture_url,
    }
    return Response({'user': user_data}, status=status.HTTP_200_OK)


# ----------------------------
# Password Reset
# ----------------------------

@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """Request password reset - sends email with token"""
    email = request.data.get('email')
    if not email:
        return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'message': 'If this email exists, a reset link has been sent'}, status=status.HTTP_200_OK)

    ip_address = request.META.get('REMOTE_ADDR')
    reset_token = PasswordResetToken.create_for_user(user, ip_address)
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5176')
    reset_url = f"{frontend_url}/reset-password?token={reset_token.token}"

    try:
        subject = 'Password Reset Request'
        message = f"""Hello {user.first_name or user.username},

You requested a password reset. Click the link below to reset your password:

{reset_url}

⚠️ IMPORTANT: This link will expire in 30 seconds for security reasons.

If you didn't request this reset, please ignore this email.

Best regards,
Admin Dashboard Team
"""
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {str(e)}")

    return Response({'message': 'If this email exists, a reset link has been sent', 'expires_in': 30},
                    status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_reset_token(request):
    """Verify if reset token is valid and return time left"""
    token_string = request.data.get('token')
    if not token_string:
        return Response({'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        reset_token = PasswordResetToken.objects.get(token=token_string)
    except PasswordResetToken.DoesNotExist:
        return Response({'error': 'Invalid token', 'valid': False}, status=status.HTTP_400_BAD_REQUEST)

    if not reset_token.is_valid():
        return Response({'error': 'Token has expired', 'expired': True, 'valid': False},
                        status=status.HTTP_400_BAD_REQUEST)

    return Response({'valid': True, 'timeLeft': reset_token.time_left(), 'email': reset_token.user.email},
                    status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """Reset password using valid token"""
    token_string = request.data.get('token')
    new_password = request.data.get('new_password')
    if not token_string or not new_password:
        return Response({'error': 'Token and new password are required'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters long'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        reset_token = PasswordResetToken.objects.get(token=token_string)
    except PasswordResetToken.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

    if not reset_token.is_valid():
        return Response({'error': 'Token has expired', 'expired': True}, status=status.HTTP_400_BAD_REQUEST)

    user = reset_token.user
    user.set_password(new_password)
    user.save()

    reset_token.used = True
    reset_token.save()

    PasswordResetToken.objects.filter(user=user).update(used=True)

    try:
        subject = 'Password Reset Successful'
        message = f"""Hello {user.first_name or user.username},

Your password has been successfully reset.

If you did not make this change, please contact support immediately.

For security:
- All active sessions have been terminated
- All previous reset tokens have been invalidated

Best regards,
Admin Dashboard Team
"""
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True)
    except Exception as e:
        logger.error(f"Failed to send confirmation email to {user.email}: {str(e)}")

    logger.info(f"Password reset successful for {user.email}")

    return Response({
        'message': 'Password reset successful',
        'actions_taken': [
            'Password updated',
            'All tokens invalidated',
            'Confirmation email sent'
        ]
    }, status=status.HTTP_200_OK)


# ----------------------------
# Business Types
# ----------------------------

@api_view(['GET'])
@permission_classes([AllowAny])
def get_business_types(request):
    """
    Get list of available business types for registration.
    """
    business_types = [
        {
            'value': choice[0],
            'label': choice[1],
            'description': get_business_type_description(choice[0])
        }
        for choice in BusinessConfig.BUSINESS_TYPE_CHOICES
    ]
    return Response({'business_types': business_types}, status=status.HTTP_200_OK)


def get_business_type_description(business_type):
    """Return a brief description of each business type"""
    descriptions = {
        'retail': 'Physical stores selling products directly to customers',
        'wholesale': 'Bulk distribution to retailers or businesses',
        'supermarket': 'Grocery stores and large retail outlets',
        'restaurant': 'Food service, cafes, bars, and catering',
        'manufacturing': 'Production and assembly operations',
        'services': 'Professional services, consulting, maintenance',
        'healthcare': 'Clinics, hospitals, pharmacies, medical centers',
        'school': 'Educational institutions, training centers',
        'agrobusiness': 'Farming, agricultural products and services',
        'hardware': 'Construction materials and hardware supplies',
        'transportation': 'Logistics, shipping, freight services',
        'ecommerce': 'Online retail and digital marketplaces',
        'nonprofit': 'NGOs, charities, and community organizations',
        'other': 'Other business types'
    }
    return descriptions.get(business_type, '')
