from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class EmailOTP(models.Model):
    otp_id = models.AutoField(primary_key=True, db_column='otp_id')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='user_id', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    otp_code = models.CharField(max_length=6, db_column='otp_code')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_in = models.IntegerField(default=300)  # 5 minutes

    class Meta:
        managed = False
        db_table = 'otp'

    def is_valid(self):
        created = self.created_at
        return timezone.now() < created + timezone.timedelta(seconds=self.expires_in)
    
    def can_resend(self, cooldown_seconds=60):
        created = self.created_at
        return (timezone.now() - created).total_seconds() >= cooldown_seconds


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('error', 'Error'),
    ]

    notification_id = models.AutoField(primary_key=True, db_column='notification_id')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='user_id')
    title = models.CharField(max_length=255, db_column='title')
    message = models.TextField(db_column='message')
    is_read = models.BooleanField(default=False, db_column='is_read')
    created_at = models.DateTimeField(auto_now_add=True, db_column='created_at')

    class Meta:
        managed = False
        db_table = 'notifications'

    def __str__(self):
        return f"{self.title} - {self.user.username}"
