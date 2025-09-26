from django.db import models

class BusinessProgram(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Ended', 'Ended'),
        ('Collected', 'Collected'),
    ]

    program_id = models.AutoField(primary_key=True)
    program_name = models.CharField(max_length=100, unique=True)
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    date_started = models.DateField()
    date_end = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    def __str__(self):
        return f"{self.program_name} ({self.status})"
    
    class Meta:
        managed = False
        db_table = "businessprogram"


class Funds(models.Model):
    fund_id = models.AutoField(primary_key=True)
    fund_name = models.CharField(max_length=100)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.fund_name} - {self.balance}"
    
    class Meta:
        managed = False
        db_table = "funds"
