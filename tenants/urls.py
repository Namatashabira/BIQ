from django.urls import path
from .views import TenantWorkerViewSet, TenantViewSet, update_school_type

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

worker_set_school_role = TenantWorkerViewSet.as_view({
    'put': 'set_school_role'
})

worker_transfer_ownership = TenantWorkerViewSet.as_view({
    'post': 'transfer_ownership'
})

urlpatterns = [
    path('', tenant_list, name='tenant-list'),
    path('<int:pk>/', tenant_detail, name='tenant-detail'),
    path('workers/', worker_list, name='worker-list'),
    path('workers/<int:pk>/', worker_detail, name='worker-detail'),
    path('workers/<int:pk>/permissions/', worker_permissions, name='worker-permissions'),
    path('workers/<int:pk>/set-school-role/', worker_set_school_role, name='worker-set-school-role'),
    path('workers/<int:pk>/transfer-ownership/', worker_transfer_ownership, name='worker-transfer-ownership'),
    path('school-type/', update_school_type, name='update-school-type'),
]
