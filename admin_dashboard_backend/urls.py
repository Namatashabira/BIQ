from django.urls import include

urlpatterns = [
    path('api/', include('api.urls')),
    path('api/students/', include('students.urls')),
]