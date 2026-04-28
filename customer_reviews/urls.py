from rest_framework.routers import DefaultRouter
from .views import CustomerReviewViewSet
from django.urls import path
from .dashboard_api import dashboard_product_reviews

router = DefaultRouter()
router.register(r'', CustomerReviewViewSet, basename='customerreview')

urlpatterns = [
    path('dashboard-reviews/', dashboard_product_reviews, name='dashboard_product_reviews'),
] + router.urls
