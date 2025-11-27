from django.db import models
from members.models import Member
from programs.models import BusinessProgram
from loans.models import Loan, LoanPenalty
from django.contrib.auth.models import User


class Dividend(models.Model):
    dividend_id = models.AutoField(primary_key=True)
    period_start = models.DateField()
    period_end = models.DateField()
    total_surplus = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=5, decimal_places=4)  # e.g., 0.0750 = 7.5%
    date_declared = models.DateField(auto_now_add=True)

    class Meta:
        db_table = 'dividends'
        managed = False


class Financialreports(models.Model):
    report_id = models.AutoField(primary_key=True, db_column='reportid')
    created_at = models.DateTimeField(auto_now_add=True, db_column='createdat')
    last_updated = models.DateTimeField(auto_now_add=True, db_column='lastupdated')
    report_type = models.CharField(max_length=50, db_column='report_type')  # e.g., 'monthly', 'dividend'
    dividend_id = models.ForeignKey(Dividend, models.DO_NOTHING, db_column='dividend_id', null=True, blank=True)

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
    add_coop_share = models.DecimalField(max_digits=12, decimal_places=2, db_column='add_coop_share')
    total_savings_investment = models.DecimalField(max_digits=12, decimal_places=2, db_column='total_savings_investment')
    dividend_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='dividend_amount')
    updated_savings_investment = models.DecimalField(max_digits=12, decimal_places=2, db_column='updated_savings_investment')
    remarks = models.TextField(db_column='remarks')

    def __str__(self):
        return f"{self.name} ({self.account_number})"
    
    class Meta:
        managed = False
        db_table = 'memberfinancialdata'


class Revenue(models.Model):
    revenue_id = models.AutoField(primary_key=True)
    source = models.CharField(max_length=50)  # e.g. 'Loan Interest', 'Service Charge', 'Penalty', 'Program Income'
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, db_column='member_id')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_collected = models.DateTimeField(auto_now_add=True)
    program_id = models.ForeignKey(BusinessProgram, models.DO_NOTHING, null=True, blank=True, db_column='program_id')
    loan_id = models.ForeignKey(Loan, models.DO_NOTHING, null=True, blank=True, db_column='loan_id')  # Assuming loan_id is an integer
    penalty_id = models.ForeignKey(LoanPenalty, models.DO_NOTHING, null=True, blank=True, db_column='penalty_id')

    class Meta:
        managed = False
        db_table = 'revenue'

class Expense(models.Model):
    expense_id = models.AutoField(primary_key=True)
    source = models.CharField(max_length=100)  # e.g. 'Service Charge', 'Utility', 'Salary'
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, blank=True, db_column='member_id')
    loan_id = models.ForeignKey(Loan, models.DO_NOTHING, null=True, blank=True, db_column='loan_id')
    date_recorded = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'expense'

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