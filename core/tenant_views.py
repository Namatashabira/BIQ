from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from tenants.models import Tenant
from core.models import BusinessConfig
from django.contrib.auth import get_user_model

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_organizations(request):
    """
    Get all tenants/organizations that the authenticated user has access to
    """
    try:
        user = request.user
        
        # Get all tenants where user is the owner or has membership
        tenants = Tenant.objects.filter(
            admin=user
        ).select_related('config')
        
        tenant_data = []
        for tenant in tenants:
            # Get user count for this tenant
            user_count = User.objects.filter(tenant=tenant).count()
            
            # Check if this is the active tenant
            is_active = request.tenant and request.tenant.id == tenant.id
            
            tenant_info = {
                'id': tenant.id,
                'name': tenant.name,
                'business_type': tenant.config.business_type if hasattr(tenant, 'config') else 'retail',
                'business_type_display': tenant.config.get_business_type_display() if hasattr(tenant, 'config') else 'Retail Store',
                'created_at': tenant.created_at,
                'is_active': is_active,
                'user_count': user_count
            }
            tenant_data.append(tenant_info)
        
        return Response({
            'success': True,
            'tenants': tenant_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def switch_tenant(request):
    """
    Switch the active tenant for the authenticated user
    """
    try:
        tenant_id = request.data.get('tenant_id')
        
        if not tenant_id:
            return Response({
                'success': False,
                'error': 'Tenant ID is required'
            }, status=400)
        
        # Get the tenant
        tenant = Tenant.objects.filter(id=tenant_id, admin=request.user).first()
        
        if not tenant:
            return Response({
                'success': False,
                'error': 'Tenant not found or you do not have access'
            }, status=404)
        
        # Update user's current tenant
        user = request.user
        user.tenant = tenant
        user.save()
        
        return Response({
            'success': True,
            'message': 'Tenant switched successfully',
            'tenant': {
                'id': tenant.id,
                'name': tenant.name
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_organization(request):
    """
    Create a new organization/tenant for an existing user
    Similar to registration but for existing authenticated users
    """
    try:
        business_name = request.data.get('business_name')
        business_type = request.data.get('business_type')
        industry_description = request.data.get('industry_description', '')
        
        if not business_name or not business_type:
            return Response({
                'success': False,
                'error': 'Business name and type are required'
            }, status=400)
        
        user = request.user

        # Prevent duplicate organization creation for the same admin
        if Tenant.objects.filter(admin=user).exists():
            return Response({
                'success': False,
                'error': 'You are already an admin of an organization. Only one organization per admin is allowed.'
            }, status=400)

        with transaction.atomic():
            # Create new tenant
            tenant = Tenant.objects.create(
                name=business_name,
                admin=user
            )
            
            # Create business configuration
            config = BusinessConfig.objects.create(
                tenant=tenant,
                business_type=business_type,
                industry_description=industry_description
            )
            
            # Apply business preset
            config.apply_business_preset()
            
            # Optionally switch to new tenant automatically
            # user.tenant = tenant
            # user.save()
            
            return Response({
                'success': True,
                'message': 'Organization created successfully',
                'tenant': {
                    'id': tenant.id,
                    'name': tenant.name,
                    'business_type': config.business_type
                }
            })
            
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
