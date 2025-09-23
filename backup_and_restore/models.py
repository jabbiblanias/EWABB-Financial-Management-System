from django.db import models
from django.contrib.auth.models import User


class Backups(models.Model):
    STORAGE_LOCATIONS = [
        ("Local", "Local"),
        ("Cloud", "Cloud"),
    ]
    BACKUP_TYPES = [
        ("Manual", "Manual"),
        ("Automatic", "Automatic"),
    ]

    backup_id = models.AutoField(primary_key=True)
    file_name = models.CharField(max_length=255)
    storage_location = models.CharField(max_length=20, choices=STORAGE_LOCATIONS)  # local path or cloud URL
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES)
    created_by = models.ForeignKey(User, models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.file_name} ({self.backup_type})"
    
    class Meta:
        managed = False
        db_table = "Backups"


class BackupRestoreLog(models.Model):
    ACTION_CHOICES = [
        ("Backup", "Backup"),
        ("Restore", "Restore"),
    ]

    STATUS_CHOICES = [
        ("Success", "Success"),
        ("Failed", "Failed"),
    ]

    log_id = models.AutoField(primary_key=True)
    backup_id = models.ForeignKey(Backups, models.DO_NOTHING)
    action = models.CharField(max_length=255, choices=ACTION_CHOICES)  # e.g., "Created backup", "Restored backup"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_by = models.ForeignKey(User, models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.status or 'N/A'}"
    
    class Meta:
        managed = False
        db_table = "backup_restore_logs"