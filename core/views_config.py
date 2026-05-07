# core/views_config.py
"""
API views for business configuration, feature toggles, and terminology.
"""
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth import get_user_model

from .business_config import (
    BusinessConfig, 
    FeatureToggle, 
    Terminology,
    Theme,
    PricingSettings,
    BUSINESS_PRESETS,
    FEATURE_DEFAULTS,
    _default_allowed_pages,
    WorkerAccessInvite,
    WorkerPageAccess,
)
from .serializers_config import (
    BusinessConfigSerializer,
    FeatureToggleSerializer,
    TerminologySerializer,
    ThemeSerializer,
    BusinessPresetSerializer,
    ApplyPresetSerializer,
    ConfigurationSummarySerializer,
    PricingSettingsSerializer,
    WorkerAccessInviteSerializer,
    WorkerPageAccessSerializer,
)
from core.auth_views import ensure_tenant_for_user
from tenants.models import TenantMembership, Tenant

User = get_user_model()


class BusinessConfigViewSet(viewsets.ModelViewSet):
    """
    API endpoint for business configuration.
    """
    serializer_class = BusinessConfigSerializer
    permission_classes = [IsAuthenticated]

    def _get_tenant(self):
        user = self.request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        return tenant
    
    def get_queryset(self):
        """Return business config for user's tenant"""
        tenant = self._get_tenant()
        if tenant:
            return BusinessConfig.objects.filter(tenant=tenant)
        return BusinessConfig.objects.none()
    
    def perform_create(self, serializer):
        """Associate with user's tenant"""
        tenant = self._get_tenant()
        if not tenant:
            raise PermissionError("User is not associated with any tenant")
        serializer.save(tenant=tenant)
    
    @action(detail=True, methods=['post'])
    def apply_preset(self, request, pk=None):
        """
        Apply a business preset to set default features and terminology.
        POST /api/business-config/{id}/apply_preset/
        Body: {"business_type": "school"}
        """
        config = self.get_object()
        serializer = ApplyPresetSerializer(data=request.data)
        
        if serializer.is_valid():
            config.business_type = serializer.validated_data['business_type']
            config.save()
            config.apply_business_preset()
            
            return Response({
                'success': True,
                'message': f'Preset applied for {config.get_business_type_display()}',
                'config': BusinessConfigSerializer(config).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FeatureToggleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for feature toggles.
    Allows enabling/disabling features per tenant.
    """
    serializer_class = FeatureToggleSerializer
    permission_classes = [IsAuthenticated]

    def _get_tenant(self):
        user = self.request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        return tenant
    
    def get_queryset(self):
        """Return feature toggles for user's tenant"""
        tenant = self._get_tenant()
        if tenant:
            return FeatureToggle.objects.filter(tenant=tenant)
        return FeatureToggle.objects.none()
    
    def perform_create(self, serializer):
        """Associate with user's tenant"""
        serializer.save(tenant=self.request.user.tenant)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update feature toggles.
        POST /api/feature-toggles/bulk_update/
        Body: {
            "features": {
                "inventory_enabled": true,
                "scheduling_enabled": false
            }
        }
        """
        # Check if user has tenant
        tenant = self._get_tenant()
        if not tenant:
            return Response(
                {'error': 'User is not associated with a tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        features = request.data.get('features', {})
        
        updated = []
        for feature_key, enabled in features.items():
            # Skip unknown feature keys to keep database clean
            if feature_key not in FEATURE_DEFAULTS:
                continue
            toggle, created = FeatureToggle.objects.update_or_create(
                tenant=tenant,
                feature_key=feature_key,
                defaults={'enabled': enabled}
            )
            updated.append(toggle)
        
        serializer = FeatureToggleSerializer(updated, many=True)
        return Response({
            'success': True,
            'message': f'{len(updated)} features updated',
            'features': serializer.data
        })


class TerminologyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for terminology/labels.
    Allows customizing business-specific terminology.
    """
    serializer_class = TerminologySerializer
    permission_classes = [IsAuthenticated]

    def _get_tenant(self):
        user = self.request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        return tenant
    
    def get_queryset(self):
        """Return terminology for user's tenant"""
        tenant = self._get_tenant()
        if tenant:
            return Terminology.objects.filter(tenant=tenant)
        return Terminology.objects.none()
    
    def perform_create(self, serializer):
        """Associate with user's tenant"""
        tenant = self._get_tenant()
        if not tenant:
            raise PermissionError("User is not associated with any tenant")
        serializer.save(tenant=tenant)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """
        Bulk update terminology.
        POST /api/terminology/bulk_update/
        Body: {
            "labels": {
                "resource": {"label": "Product", "label_plural": "Products"},
                "transaction": {"label": "Order", "label_plural": "Orders"}
            }
        }
        """
        labels = request.data.get('labels', {})
        tenant = request.user.tenant
        
        updated = []
        for entity, label_data in labels.items():
            term, created = Terminology.objects.update_or_create(
                tenant=tenant,
                entity=entity,
                defaults={
                    'label': label_data.get('label', entity.title()),
                    'label_plural': label_data.get('label_plural', entity.title() + 's')
                }
            )
            updated.append(term)
        
        serializer = TerminologySerializer(updated, many=True)
        return Response({
            'success': True,
            'message': f'{len(updated)} labels updated',
            'labels': serializer.data
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_business_presets(request):
    """
    Get available business presets.
    GET /api/business-presets/
    """
    presets = []
    
    for type_key, preset_data in BUSINESS_PRESETS.items():
        # Get display name from choices
        display_name = dict(BusinessConfig.BUSINESS_TYPE_CHOICES).get(type_key, type_key.title())
        
        presets.append({
            'type': type_key,
            'display_name': display_name,
            'description': f'Default configuration for {display_name}',
            'features': preset_data['features'],
            'terminology': preset_data['terminology']
        })
    
    return Response({
        'success': True,
        'presets': presets
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_configuration_summary(request):
    """
    Get complete configuration summary for frontend.
    Returns features and labels in a single call.
    GET /api/configuration/
    
    Returns:
    {
        "business_type": "school",
        "features": {
            "inventory_enabled": false,
            "scheduling_enabled": true
        },
        "labels": {
            "resource": "Subject",
            "resource_plural": "Subjects",
            "transaction": "Enrollment",
            "transaction_plural": "Enrollments"
        },
        "onboarding_completed": true
    }
    """
    user = request.user

    tenant = getattr(user, 'tenant', None)
    if not tenant:
        membership = TenantMembership.objects.filter(user=user).first()
        tenant = membership.tenant if membership else None

    # Auto-create/verify tenant so authenticated users can load config
    if not tenant:
        tenant = ensure_tenant_for_user(user)
    elif hasattr(tenant, 'is_verified') and not tenant.is_verified:
        tenant.is_verified = True
        tenant.save(update_fields=['is_verified'])
    
    # Get or create business config
    config, created = BusinessConfig.objects.get_or_create(
        tenant=tenant,
        defaults={'business_type': 'other'}
    )
    
    # Ensure all default features exist in DB, then build dict
    for feature_key, default_enabled in FEATURE_DEFAULTS.items():
        FeatureToggle.objects.get_or_create(
            tenant=tenant,
            feature_key=feature_key,
            defaults={'enabled': default_enabled}
        )

    features = {}
    for toggle in FeatureToggle.objects.filter(tenant=tenant):
        features[toggle.feature_key] = toggle.enabled
    
    # Get labels as flat dict
    labels = {}
    for term in Terminology.objects.filter(tenant=tenant):
        labels[term.entity] = term.label
        labels[f"{term.entity}_plural"] = term.label_plural
    
    # Get theme
    theme_data = {}
    try:
        theme = Theme.objects.get(tenant=tenant)
        theme_data = {
            'primary_color': theme.primary_color,
            'secondary_color': theme.secondary_color,
            'accent_color': theme.accent_color,
            'logo_url': theme.logo.url if theme.logo else None,
            # Backward compatibility: expose selected_palette_id as color hex
            'selected_palette_id': getattr(theme, 'selected_palette_id', None) or theme.color,
            'color': theme.color,
        }
    except Theme.DoesNotExist:
        pass

    # Pricing settings (ensure defaults exist)
    pricing_settings, _ = PricingSettings.objects.get_or_create(
        tenant=tenant,
        defaults=PricingSettings.default_values()
    )
    pricing_data = PricingSettingsSerializer(pricing_settings).data

    # Page access for current user
    if getattr(user, 'role', '') in ['tenant_admin', 'superadmin'] or getattr(user, 'is_staff', False):
        allowed_pages = _default_allowed_pages()
    else:
        try:
            access = WorkerPageAccess.objects.get(tenant=tenant, user=user)
            allowed_pages = access.allowed_pages or []
        except WorkerPageAccess.DoesNotExist:
            # Fallback: read from Worker.pages if WorkerPageAccess not yet created
            from tenants.models import Worker
            try:
                worker_rec = Worker.objects.get(tenant=tenant, user=user)
                raw = worker_rec.pages or {}
                allowed_pages = list(raw.keys()) if isinstance(raw, dict) else list(raw)
                # Back-fill WorkerPageAccess so future calls are fast
                if allowed_pages:
                    WorkerPageAccess.objects.create(
                        tenant=tenant, user=user, allowed_pages=allowed_pages
                    )
            except Worker.DoesNotExist:
                allowed_pages = []

    def first_accessible_path():
        nav_order = [
            ('dashboard_enabled', '/dashboard'),
            ('organizations_enabled', '/my-organizations'),
            ('product_enabled', '/product'),
            ('inventory_enabled', '/inventory'),
            ('orders_enabled', '/orders'),
            ('customers_enabled', '/customers'),
            ('scheduling_enabled', '/appointments'),
            ('manual_entry_enabled', '/manual-entry'),
            ('payments_enabled', '/receipt-lookup'),
            ('analytics_enabled', '/analytics'),
            ('ai_insights_enabled', '/ai-insights'),
            ('accounting_enabled', '/accounting'),
            ('enrollment_enabled', '/enrollment'),
        ]

        # Admins can see anything that is feature-enabled
        is_admin = getattr(user, 'role', '') in ['tenant_admin', 'superadmin'] or getattr(user, 'is_staff', False)
        for key, path in nav_order:
            if not features.get(key, True):
                continue
            if is_admin:
                return path
            if key in allowed_pages:
                return path
        return '/dashboard'
    
    return Response({
        'business_type': config.business_type,
        'features': features,
        'labels': labels,
        'theme': theme_data,
        'pricing_settings': pricing_data,
        'allowed_pages': allowed_pages,
        'first_accessible_path': first_accessible_path(),
        'onboarding_completed': config.onboarding_completed
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_onboarding(request):
    """
    Mark onboarding as complete.
    POST /api/configuration/complete-onboarding/
    """
    user = request.user
    
    if not hasattr(user, 'tenant'):
        return Response({
            'error': 'User has no tenant'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    config, created = BusinessConfig.objects.get_or_create(
        tenant=user.tenant,
        defaults={'business_type': 'other'}
    )
    
    config.onboarding_completed = True
    config.save()
    
    return Response({
        'success': True,
        'message': 'Onboarding completed'
    })


class WorkerAccessInviteView(APIView):
    """Create/list worker invites with one-time password."""
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, user):
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        return tenant

    def get(self, request):
        tenant = self._get_tenant(request.user)
        if not tenant:
            return Response({'error': 'User has no tenant'}, status=status.HTTP_400_BAD_REQUEST)
        invites = WorkerAccessInvite.objects.filter(tenant=tenant)
        return Response(WorkerAccessInviteSerializer(invites, many=True).data)

    def post(self, request):
        user = request.user
        if not getattr(user, 'role', '') in ['tenant_admin', 'superadmin'] and not user.is_staff:
            return Response({'error': 'Only admins can create invites'}, status=status.HTTP_403_FORBIDDEN)

        tenant = self._get_tenant(user)
        if not tenant:
            return Response({'error': 'User has no tenant'}, status=status.HTTP_400_BAD_REQUEST)

        name  = (request.data.get('name') or '').strip()
        email = (request.data.get('email') or '').strip()
        username = (request.data.get('username') or '').strip()
        school_role = (request.data.get('school_role') or '').strip()
        allowed_pages = list(request.data.get('allowed_pages') or [])

        if not name or not email or not username:
            return Response({'error': 'name, email and username are required'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exclude(email=email).exists():
            return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)

        invite, _ = WorkerAccessInvite.objects.get_or_create(
            tenant=tenant,
            email=email,
            defaults={
                'name': name,
                'username': username,
                'school_role': school_role,
                'allowed_pages': allowed_pages,
                'created_by': user,
                'otp_code': WorkerAccessInvite.generate_otp(),
                'otp_expires_at': timezone.now(),
            }
        )

        invite.name = name
        invite.username = username
        invite.school_role = school_role
        invite.allowed_pages = allowed_pages
        invite.created_by = user
        invite.refresh_otp()
        invite.save()

        return Response(
            {'success': True, 'invite': WorkerAccessInviteSerializer(invite).data},
            status=status.HTTP_201_CREATED
        )


class WorkerAccessActivateView(APIView):
    """Allow a worker to redeem an invite and set password using username + OTP."""
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        otp      = (request.data.get('otp') or '').strip()
        password = (request.data.get('password') or '').strip()

        # Support lookup by username or email
        invite = (
            WorkerAccessInvite.objects.filter(username=username, otp_code=otp, used=False).first()
            or WorkerAccessInvite.objects.filter(email=username, otp_code=otp, used=False).first()
        )
        if not invite:
            return Response({'error': 'Invalid username or OTP code'}, status=status.HTTP_400_BAD_REQUEST)

        if invite.otp_expires_at < timezone.now():
            return Response({'error': 'OTP code has expired'}, status=status.HTTP_400_BAD_REQUEST)

        if not password or len(password) < 6:
            return Response({'error': 'Password must be at least 6 characters'}, status=status.HTTP_400_BAD_REQUEST)

        actual_username = invite.username or invite.email.split('@')[0]
        user, created = User.objects.get_or_create(
            email=invite.email,
            defaults={
                'username': actual_username,
                'first_name': invite.name.split()[0] if invite.name else '',
                'last_name': ' '.join(invite.name.split()[1:]) if invite.name else '',
                'tenant': invite.tenant,
                'role': 'worker',
            }
        )
        user.username = actual_username
        user.tenant = invite.tenant
        user.role = 'worker'
        user.set_password(password)
        user.save()

        WorkerPageAccess.objects.update_or_create(
            tenant=invite.tenant,
            user=user,
            defaults={'allowed_pages': invite.allowed_pages}
        )

        # Create/update Worker record with school_role
        from tenants.models import Worker
        ROLE_PAGES = {
            'teacher':     ['marks-entry', 'attendance'],
            'bursar':      ['fees', 'school-receipt-lookup'],
            'dos':         ['student-management', 'marks-entry', 'report-templates', 'attendance'],
            'deputy':      ['student-management', 'marks-entry', 'fees', 'report-templates', 'attendance'],
            'headteacher': ['dashboard', 'student-management', 'marks-entry', 'fees', 'report-templates', 'attendance', 'analytics'],
            'director':    ['dashboard', 'student-management', 'marks-entry', 'fees', 'report-templates', 'attendance', 'analytics'],
        }
        worker, _ = Worker.objects.get_or_create(tenant=invite.tenant, user=user)
        if invite.school_role:
            worker.school_role = invite.school_role
            worker.pages = {p: True for p in ROLE_PAGES.get(invite.school_role, [])}
            worker.save()

        invite.used = True
        invite.save(update_fields=['used'])

        return Response({'success': True, 'message': 'Account activated. You can now log in.'})


class WorkerAccessCheckOtpView(APIView):
    """Validate OTP by username and return invite info (name, role) if valid."""
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or request.data.get('email') or '').strip()
        otp      = (request.data.get('otp') or '').strip()

        invite = (
            WorkerAccessInvite.objects.filter(username=username, otp_code=otp, used=False).first()
            or WorkerAccessInvite.objects.filter(email=username, otp_code=otp, used=False).first()
        )
        if not invite:
            return Response({'valid': False, 'reason': 'not_found'}, status=status.HTTP_200_OK)

        if invite.otp_expires_at < timezone.now():
            return Response({'valid': False, 'reason': 'expired'}, status=status.HTTP_200_OK)

        return Response({
            'valid': True,
            'name': invite.name,
            'email': invite.email,
            'username': invite.username,
            'school_role': invite.school_role,
        }, status=status.HTTP_200_OK)


class WorkerPageAccessView(APIView):
    """Get or set allowed pages for a worker."""
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, user):
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        return tenant

    def get(self, request):
        tenant = self._get_tenant(request.user)
        if not tenant:
            return Response({'error': 'User has no tenant'}, status=status.HTTP_400_BAD_REQUEST)

        # Admins get full list; workers without record get none
        if getattr(request.user, 'role', '') in ['tenant_admin', 'superadmin'] or getattr(request.user, 'is_staff', False):
            allowed = _default_allowed_pages()
        else:
            try:
                access = WorkerPageAccess.objects.get(tenant=tenant, user=request.user)
                allowed = access.allowed_pages or []
            except WorkerPageAccess.DoesNotExist:
                allowed = []

        return Response({'allowed_pages': allowed})

    def post(self, request):
        # Only admins can assign page access
        user = request.user
        if not getattr(user, 'role', '') in ['tenant_admin', 'superadmin'] and not user.is_staff:
            return Response({'error': 'Only admins can assign access'}, status=status.HTTP_403_FORBIDDEN)

        tenant = self._get_tenant(user)
        if not tenant:
            return Response({'error': 'User has no tenant'}, status=status.HTTP_400_BAD_REQUEST)

        target_email = request.data.get('email') or ''
        target_user_id = request.data.get('user_id')
        allowed_pages = request.data.get('allowed_pages')
        allowed_pages = [p for p in (allowed_pages or []) if p in FEATURE_DEFAULTS]
        # Permit empty lists to intentionally remove access; default to none assigned
        if allowed_pages is None:
            allowed_pages = []

        target_user = None
        if target_user_id:
            target_user = User.objects.filter(id=target_user_id, tenant=tenant).first()
        if not target_user and target_email:
            target_user = User.objects.filter(email=target_email, tenant=tenant).first()

        if not target_user:
            return Response({'error': 'Target user not found'}, status=status.HTTP_404_NOT_FOUND)

        access, _ = WorkerPageAccess.objects.update_or_create(
            tenant=tenant,
            user=target_user,
            defaults={'allowed_pages': allowed_pages}
        )

        return Response({'success': True, 'access': WorkerPageAccessSerializer(access).data})


class PricingSettingsView(APIView):
    """CRUD-lite endpoint for global pricing/currency settings per tenant."""
    permission_classes = [IsAuthenticated]

    def _get_tenant(self, request):
        user = request.user
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            membership = TenantMembership.objects.filter(user=user).first()
            tenant = membership.tenant if membership else None
        if tenant:
            return tenant
        return ensure_tenant_for_user(user)

    def get(self, request):
        tenant = self._get_tenant(request)
        if not tenant:
            return Response({'error': 'No tenant available'}, status=status.HTTP_404_NOT_FOUND)

        settings_obj, _ = PricingSettings.objects.get_or_create(
            tenant=tenant,
            defaults=PricingSettings.default_values()
        )
        return Response(PricingSettingsSerializer(settings_obj).data)

    def post(self, request):
        tenant = self._get_tenant(request)
        if not tenant:
            return Response({'error': 'User has no tenant'}, status=status.HTTP_400_BAD_REQUEST)

        settings_obj, _ = PricingSettings.objects.get_or_create(
            tenant=tenant,
            defaults=PricingSettings.default_values()
        )
        serializer = PricingSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    put = post
    patch = post


class ThemeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for theme management.
    """
    serializer_class = ThemeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return theme for user's tenant"""
        user = self.request.user
        if hasattr(user, 'tenant'):
            return Theme.objects.filter(tenant=user.tenant)
        return Theme.objects.none()
    
    def perform_create(self, serializer):
        """Associate with user's tenant"""
        serializer.save(tenant=self.request.user.tenant)
    
    @action(detail=False, methods=['post'])
    def update_colors(self, request):
        """
        Update theme color identifier.
        POST /api/theme/update_colors/
        Body: {
            "color": "#3B82F6"  // Primary color identifier
        }
        """
        if not hasattr(request.user, 'tenant'):
            return Response(
                {'error': 'User has no tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant = request.user.tenant
        theme, created = Theme.objects.get_or_create(tenant=tenant)
        
        # Update color identifier
        if 'color' in request.data:
            theme.color = request.data['color']
        elif 'primary_color' in request.data:
            # Support legacy API - use primary color as identifier
            theme.color = request.data['primary_color']
        
        theme.save()
        
        serializer = ThemeSerializer(theme, context={'request': request})
        return Response({
            'success': True,
            'message': 'Theme colors updated',
            'theme': serializer.data
        })    
    def update(self, request, *args, **kwargs):
        """
        Update theme with logo and color identifier.
        PUT/PATCH /api/theme/<id>/
        """
        if not hasattr(request.user, 'tenant'):
            return Response(
                {'error': 'User has no tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tenant = request.user.tenant
        theme, created = Theme.objects.get_or_create(tenant=tenant)
        
        # Update color identifier if provided
        if 'color' in request.data:
            theme.color = request.data['color']
        elif 'primary_color' in request.data:
            # Support legacy API - use primary color as identifier
            theme.color = request.data['primary_color']
        
        # Update logo if provided
        if 'logo' in request.FILES:
            theme.logo = request.FILES['logo']
        
        theme.save()
        
        serializer = ThemeSerializer(theme, context={'request': request})
        return Response({
            'success': True,
            'message': 'Theme updated successfully',
            'theme': serializer.data
        })