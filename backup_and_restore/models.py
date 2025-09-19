from django.db import models
from django.contrib.auth.models import User


class Backup(models.Model):
    BACKUP_TYPES = [
        ("Manual Backup", "Manual Backup"),
        ("Auto Backup", "Auto Backup"),
    ]

    backup_id = models.AutoField(primary_key=True)
    file_name = models.CharField(max_length=255)
    storage_location = models.CharField(max_length=500)  # local path or cloud URL
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, models.DO_NOTHING)

    def __str__(self):
        return f"{self.file_name} ({self.backup_type})"
    
    class Meta:
        managed = False
        db_table = "Backup"


class BackupRestoreLog(models.Model):
    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("PENDING", "Pending"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    action = models.CharField(max_length=255)  # e.g., "Created backup", "Restored backup"
    related_backup = models.ForeignKey(
        Backup, on_delete=models.SET_NULL, null=True, blank=True, related_name="logs"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.action} - {self.status or 'N/A'}"
    
    class Meta:
        managed = False
        db_table = ""