from django.db import models
from django.contrib.auth.models import User


class BackupSetting(models.Model):
    STORAGE_LOCATIONS = [
        ("Local", "Local"),
        ("Cloud", "Cloud"),
    ]
    BACKUP_TYPES = [
        ("Manual", "Manual"),
        ("Automatic", "Automatic"),
    ]

    backup_setting_id = models.AutoField(primary_key=True)
    frequency = models.CharField(max_length=255)
    storage_location = models.CharField(max_length=20, choices=STORAGE_LOCATIONS)
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES)
    user_id = models.ForeignKey(User, on_delete=models.DO_NOTHING, db_column='user_id')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.backup_setting_id} ({self.backup_type})"

    class Meta:
        managed = False
        db_table = "backup_setting"


'''class BackupRestoreLog(models.Model):
    ACTION_CHOICES = [
        ("Backup", "Backup"),
        ("Restore", "Restore"),
    ]

    STATUS_CHOICES = [
        ("Success", "Success"),
        ("Failed", "Failed"),
    ]

    log_id = models.AutoField(primary_key=True)
    backup_setting_id = models.ForeignKey(BackupSetting, models.DO_NOTHING)
    action = models.CharField(max_length=255, choices=ACTION_CHOICES)  # e.g., "Created backup", "Restored backup"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_by = models.ForeignKey(User, models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.status or 'N/A'}"
    
    class Meta:
        managed = False
        db_table = "backup_restore_logs"'''