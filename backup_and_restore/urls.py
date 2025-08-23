from django.urls import path
from . import views

urlpatterns = [
    path('', views.backup_and_restore_view, name='backup_and_restore'),
]