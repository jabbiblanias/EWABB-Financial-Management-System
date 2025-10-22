from django.db import models
from django.contrib.auth.models import User

class CashierStatus(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('on_break', 'On Break'),
        ('unavailable', 'Unavailable'),
    ]
    status_id = models.AutoField(primary_key=True)
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column="user_id")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cashier Status: {self.get_status_display()} (Updated at: {self.updated_at})"
    
    class Meta:
        db_table = 'cashier_status'
        managed = False