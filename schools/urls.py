from django.urls import path
from . import views

urlpatterns = [
    path('marks-entry/', views.marks_entry, name='marks_entry'),
    path('fees/', views.fees_page, name='fees_page'),
]