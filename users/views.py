from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.http import JsonResponse
from .models import UserProfile, UserTenantMembership
from .serializers import UserRegisterSerializer, UserProfileSerializer, UserWithProfileSerializer
from .forms import UserTenantMembershipForm

User = get_user_model()


def _bootstrap_tenant_config(tenant):
    """Initialize default features, terminology, and pricing for a new self-signup tenant."""
    try:
        from core.business_config import (
            BusinessConfig, FeatureToggle, Terminology, PricingSettings,
            FEATURE_DEFAULTS, BUSINESS_PRESETS
        )
        # BusinessConfig
        BusinessConfig.objects.get_or_create(
            tenant=tenant,
            defaults={'business_type': 'other', 'onboarding_completed': False}
        )
        # Feature toggles — all defaults enabled
        for key, enabled in FEATURE_DEFAULTS.items():
            FeatureToggle.objects.get_or_create(
                tenant=tenant, feature_key=key,
                defaults={'enabled': enabled}
            )
        # Terminology — use 'other' preset
        preset_terms = BUSINESS_PRESETS.get('other', {}).get('terminology', {})
        for entity, label in preset_terms.items():
            Terminology.objects.get_or_create(
                tenant=tenant, entity=entity,
                defaults={'label': label, 'label_plural': label + 's'}
            )
        # Pricing settings
        PricingSettings.objects.get_or_create(tenant=tenant)
    except Exception as e:
        # Non-fatal — tenant still works without config
        import logging
        logging.getLogger(__name__).warning(f'Bootstrap config failed for tenant {tenant.id}: {e}')


# -------------------------------
# Guest Profile APIs
# -------------------------------
class GuestProfileView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        guest_token = request.data.get('guest_token')
        if not guest_token:
            guest_token = get_random_string(32)

        profile, _ = UserProfile.objects.get_or_create(guest_token=guest_token)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({'guest_token': guest_token, 'profile': serializer.data})

    def patch(self, request):
        guest_token = request.data.get('guest_token')
        if not guest_token:
            return Response({'error': 'guest_token required'}, status=400)

        try:
            profile = UserProfile.objects.get(guest_token=guest_token)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)

        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'guest_token': guest_token, 'profile': serializer.data})


# -------------------------------
# Register from Guest API
# -------------------------------
class RegisterFromGuestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        guest_token = request.data.get('guest_token')
        password = request.data.get('password')
        email = request.data.get('email')

        if not guest_token or not password:
            return Response({'error': 'guest_token and password required'}, status=400)

        # Get or create guest profile
        profile, _ = UserProfile.objects.get_or_create(guest_token=guest_token)

        # Ensure username is not empty
        username = request.data.get('username') or profile.name or f"user_{get_random_string(6)}"

        # Prepare user data
        user_data = {
            'email': email or profile.email,
            'username': username,
            'password': password
        }


        # Serialize and save user
        user_serializer = UserRegisterSerializer(data=user_data)
        try:
            user_serializer.is_valid(raise_exception=True)
            user = user_serializer.save()
        except Exception as e:
            return Response({'error': str(e)}, status=500)

        # Automatically create a Tenant for this user (super admin of their own account)
        from tenants.models import Tenant
        try:
            tenant = Tenant.objects.create(
                name=f"{username}'s Organization",
                admin=user,
                is_verified=True,  # Self-signup tenants are auto-verified
            )
        except Exception as e:
            user.delete()
            return Response({'error': f"Tenant creation failed: {str(e)}"}, status=500)

        # Link profile to user safely
        profile.user = user
        profile.guest_token = None
        try:
            profile.save()
        except Exception as e:
            user.delete()
            tenant.delete()
            return Response({'error': f"Profile save failed: {str(e)}"}, status=500)

        # Link user to tenant
        user.tenant = tenant
        try:
            user.save(update_fields=['tenant'])
        except Exception:
            pass

        # Bootstrap tenant config (features, terminology, pricing)
        _bootstrap_tenant_config(tenant)

        # Issue JWT tokens so user can log in immediately
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response({
            'user': user_serializer.data,
            'profile': UserProfileSerializer(profile).data,
            'tenant': {'id': tenant.id, 'uuid': str(tenant.uuid), 'name': tenant.name},
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })


# -------------------------------
# Registered User Profile APIs
# -------------------------------
class UserProfileRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = UserWithProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if not user.is_tenant_verified:
            raise PermissionError('Tenant account is not verified. Please contact support.')
        return user


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload profile picture to Cloudinary and save URL."""
    file = request.FILES.get('profile_picture')
    if not file:
        return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.profile_picture = file
    profile.save(update_fields=['profile_picture'])

    try:
        url = profile.profile_picture.url
    except Exception:
        url = None

    return Response({'profile_picture_url': url}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """Get current user's profile information"""
    try:
        user = request.user
        if not user.is_tenant_verified:
            return Response({'error': 'Tenant account is not verified. Please contact support.'}, status=403)
        serializer = UserWithProfileSerializer(user)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """Update current user's profile information"""
    try:
        user = request.user
        if not user.is_tenant_verified:
            return Response({'error': 'Tenant account is not verified. Please contact support.'}, status=403)
        serializer = UserWithProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# Multi-tenant Membership API
# -------------------------------
@api_view(['POST'])
@permission_classes([IsAdminUser])
def connect_user_to_tenant(request):
    """Connect a user to a tenant (admin only)"""
    form = UserTenantMembershipForm(request.data)
    if form.is_valid():
        membership = form.save()
        return Response({'success': True, 'membership_id': membership.id})
    return Response({'success': False, 'errors': form.errors}, status=400)


# -------------------------------
# AJAX validation APIs
# -------------------------------
@api_view(['GET'])
@permission_classes([AllowAny])
def check_email_exists(request):
    email = request.GET.get('email')
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({'exists': exists})


@api_view(['GET'])
@permission_classes([AllowAny])
def check_username_exists(request):
    username = request.GET.get('username')
    exists = User.objects.filter(username=username).exists()
    return JsonResponse({'exists': exists})


# ───────────────────────────────────────────────────────────────────────────
# Superadmin User Management APIs
# ───────────────────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_list_all_users(request):
    """Superadmin only: Get all users with their status and activity"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Only superadmin can access this.'}, status=status.HTTP_403_FORBIDDEN)

    from django.utils import timezone
    from datetime import timedelta

    users = User.objects.all().select_related('profile').order_by('-last_login')
    
    users_data = []
    for user in users:
        profile = user.profile if hasattr(user, 'profile') else None
        last_login = user.last_login
        is_online = last_login and (timezone.now() - last_login) < timedelta(minutes=5)

        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'name': profile.name if profile else user.first_name or user.username,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'is_active': user.is_active,
            'is_online': is_online,
            'last_login': last_login.isoformat() if last_login else None,
            'date_joined': user.date_joined.isoformat(),
            'tenant_name': user.tenant.name if hasattr(user, 'tenant') and user.tenant else 'N/A',
        })

    return Response(users_data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def admin_delete_user(request, user_id):
    """Superadmin only: Delete a user"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Only superadmin can delete users.'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.id == user_id:
        return Response({'error': 'Cannot delete yourself.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
        username = user.username
        user.delete()
        return Response({'message': f'User {username} deleted successfully.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_deactivate_user(request, user_id):
    """Superadmin only: Deactivate a user account"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Only superadmin can deactivate users.'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.id == user_id:
        return Response({'error': 'Cannot deactivate yourself.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({'message': f'User {user.username} deactivated.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_reactivate_user(request, user_id):
    """Superadmin only: Reactivate a deactivated user account"""
    if not (request.user.is_staff and request.user.is_superuser):
        return Response({'error': 'Only superadmin can reactivate users.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response({'message': f'User {user.username} reactivated.'})
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
