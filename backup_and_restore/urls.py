from django.urls import path
from . import views

urlpatterns = [
    path('', views.backup_and_restore_view, name='backup_and_restore'),
    path("manual-backup/", views.manual_backup, name="manual_backup"),
    path("restore/", views.restore_from_drive, name="restore"),
]