from django.db import models
from members.models import Member
from django.contrib.auth.models import User


class Financialreports(models.Model):
    report_id = models.AutoField(primary_key=True, db_column='reportid')
    title = models.CharField(max_length=255, db_column='title')
    created_at = models.DateTimeField(auto_now_add=True, db_column='createdat')
    status = models.CharField(max_length=20, db_column='status')
    last_updated = models.DateTimeField(auto_now_add=True, db_column='lastupdated')

    def __str__(self):
        return f"{self.name} ({self.account_number})"
    
    class Meta:
        managed = False
        db_table = 'financialreports'
    

class Memberfinancialdata(models.Model):
    member_financial_id = models.AutoField(primary_key=True, db_column='memberfinancialid')
    report_id = models.ForeignKey(Financialreports, models.DO_NOTHING, db_column='reportid')
    account_number = models.CharField(max_length=50, db_column='accountnumber')
    name = models.CharField(max_length=150, db_column='name')
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, db_column='outstandingbalance')
    date_loaned = models.DateField(db_column='lastdateloaned', blank=True, null=True)
    savings = models.DecimalField(max_digits=12, decimal_places=2, db_column='savings')
    penalty_charge = models.DecimalField(max_digits=12, decimal_places=2, db_column='penaltycharge')
    savings_after_deduction = models.DecimalField(max_digits=12, decimal_places=2, db_column='savingsafterdeduction')
    remarks = models.TextField(db_column='remarks')

    def __str__(self):
        return f"{self.name} ({self.account_number})"
    
    class Meta:
        managed = False
        db_table = 'memberfinancialdata'


class Revenue(models.Model):
    revenue_id = models.AutoField(primary_key=True)
    source = models.CharField(max_length=50)  # e.g. 'Loan Interest', 'Service Charge', 'Penalty', 'Program Income'
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_collected = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='recorded_by')

    class Meta:
        managed = False
        db_table = 'revenue'

class Expense(models.Model):
    expense_id = models.AutoField(primary_key=True)
    source = models.CharField(max_length=100)  # e.g. 'Service Charge', 'Utility', 'Salary'
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_recorded = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, db_column='recorded_by')

    class Meta:
        managed = False
        db_table = 'expense'