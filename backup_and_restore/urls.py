from django.urls import path
from . import views

urlpatterns = [
    path('', views.backup_and_restore_view, name='backup_and_restore'),
    path("manual-backup/", views.manual_backup, name="manual_backup"),
    path("auto-backup/setting/", views.auto_backup_setting, name="auto_backup_setting"),
    path("restore/", views.restore_from_drive, name="restore"),
    path('automatic-backup/', views.run_automatic_backup, name="automatic_backup"),
    
]