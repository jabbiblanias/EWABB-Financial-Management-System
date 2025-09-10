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
        if timezone.is_naive(created):
            created = timezone.make_aware(created, timezone.get_current_timezone())
        return (timezone.now() - created).total_seconds() < self.expires_in

