from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_plans, name='list-plans'),
    path('my-subscription/', views.my_subscription, name='my-subscription'),
    path('select/', views.select_plan, name='select-plan'),
    path('check-product-limit/', views.check_product_limit, name='check-product-limit'),

    # Payment flow
    path('payment-request/', views.submit_payment_request, name='submit-payment-request'),
    path('payment-profile/', views.payment_profile, name='payment-profile'),
    path('activate/', views.activate_plan, name='activate-plan'),
    path('poll-code/', views.poll_activation_code, name='poll-activation-code'),

    # Admin
    path('admin/payment-requests/', views.admin_list_payment_requests, name='admin-payment-requests'),
    path('admin/payment-requests/<int:pk>/generate-code/', views.admin_generate_code, name='admin-generate-code'),
    path('admin/payment-requests/<int:pk>/reject/', views.admin_reject_request, name='admin-reject-request'),
]
