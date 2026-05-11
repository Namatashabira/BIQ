from django.urls import path
from . import views

urlpatterns = [
    path('generate/', views.generate_comment, name='ai-comment-generate'),
    path('student/<str:student_id>/', views.get_comment, name='ai-comment-get'),
    path('<int:pk>/update/', views.update_comment, name='ai-comment-update'),
]
