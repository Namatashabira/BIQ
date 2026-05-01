from django.urls import path
from . import views

urlpatterns = [
    path('', views.list_plans, name='list-plans'),
    path('my-subscription/', views.my_subscription, name='my-subscription'),
    path('select/', views.select_plan, name='select-plan'),
    path('check-product-limit/', views.check_product_limit, name='check-product-limit'),
]
