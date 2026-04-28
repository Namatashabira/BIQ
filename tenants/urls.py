from django.urls import path
from .views import TenantWorkerViewSet, TenantViewSet

# Tenant endpoints
tenant_list = TenantViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

tenant_detail = TenantViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'delete': 'destroy'
})

# Worker endpoints
worker_list = TenantWorkerViewSet.as_view({
    'get': 'list',
    'post': 'create'
})

worker_detail = TenantWorkerViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'delete': 'destroy'
})

worker_permissions = TenantWorkerViewSet.as_view({
    'put': 'permissions'
})

urlpatterns = [
    # Tenant management
    path('', tenant_list, name='tenant-list'),
    path('<int:pk>/', tenant_detail, name='tenant-detail'),
    
    # Worker management
    path('workers/', worker_list, name='worker-list'),
    path('workers/<int:pk>/', worker_detail, name='worker-detail'),
    path('workers/<int:pk>/permissions/', worker_permissions, name='worker-permissions'),
]
