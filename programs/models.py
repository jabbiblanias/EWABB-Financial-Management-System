from django.db import models

class BusinessProgram(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Ended', 'Ended'),
        ('Collected', 'Collected'),
    ]

    program_id = models.AutoField(primary_key=True, db_column="programid")
    program_name = models.CharField(max_length=100, unique=True, db_column="programname")
    total_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, db_column="totalprofit")
    date_started = models.DateTimeField(db_column="datestarted")
    date_end = models.DateTimeField(db_column="dateend")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active', db_column="status")

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
