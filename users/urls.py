from django.urls import path
from . import views
from .public_auth_views import PublicUserRegisterView
from .public_login_views import PublicUserLoginView

urlpatterns = [
    # Public user registration (separate from tenant auth)
    path('public/register/', PublicUserRegisterView.as_view(), name='public-user-register'),
    # Public user login (separate from tenant auth)
    path('public/login/', PublicUserLoginView.as_view(), name='public-user-login'),
    # Registered user profile
    path('profile/', views.UserProfileRetrieveUpdateView.as_view(), name='user-profile'),

    # Guest profile endpoints
    path('profile/guest/', views.GuestProfileView.as_view(), name='guest-profile'),
    path('profile/register/', views.RegisterFromGuestView.as_view(), name='register-from-guest'),

    # Additional profile APIs
    path('profile/get/', views.get_user_profile, name='get-user-profile'),
    path('profile/update/', views.update_user_profile, name='update-user-profile'),

    # Connect user to tenant (admin only)
    path('connect/', views.connect_user_to_tenant, name='connect_user_to_tenant'),

    # AJAX endpoints for validation
    path('core/auth/check-email/', views.check_email_exists, name='check-email'),
    path('core/auth/check-username/', views.check_username_exists, name='check-username'),
]
