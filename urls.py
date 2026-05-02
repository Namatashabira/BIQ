from django.urls import include

urlpatterns += [
    path('schools/', include('schools.urls')),
]