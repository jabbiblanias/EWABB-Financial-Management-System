from django.db import models
from django.contrib.auth.models import User
from members.models import Member


class LoanApplication(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    loan_application_id = models.AutoField(primary_key=True, db_column='loanapplicationid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    loan_type = models.CharField(max_length=50, db_column='loantype')
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='loanamount')
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, db_column='interestrate')
    loan_term_years = models.PositiveIntegerField(db_column='loantermyears')
    loan_term_months = models.PositiveIntegerField(db_column='loantermmonths')
    loan_term_days = models.PositiveIntegerField(db_column='loantermdays')
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, db_column='totalpayable')
    monthly_amortization = models.DecimalField(max_digits=12, decimal_places=2, db_column='monthlyamortization')
    cbu = models.DecimalField(max_digits=12, decimal_places=2, db_column='cbu')
    insurance = models.DecimalField(max_digits=12, decimal_places=2, db_column='insurance')
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, db_column='servicecharge')
    net_proceeds = models.DecimalField(max_digits=12, decimal_places=2, db_column='netproceeds')
    application_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    verifier_id = models.ForeignKey(User, related_name='verified_loans', on_delete=models.SET_NULL, null=True, blank=True, db_column='verifierid')
    verified_date = models.DateField(null=True, blank=True, db_column='verifieddate')
    approver_id = models.ForeignKey(User, related_name='approved_loans', on_delete=models.SET_NULL, null=True, blank=True, db_column='approverid')
    approved_date = models.DateField(null=True, blank=True, db_column='approveddate')

    def __str__(self):
        return f"Loan Application #{self.id} - {self.member}"


class Loan(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Completed', 'Completed'),
    ]

    loan_id = models.AutoField(primary_key=True, db_column='loanid')
    loan_application_id = models.ForeignKey(LoanApplication, models.DO_NOTHING, db_column='loanapplicationid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, db_column='outstandingbalance')
    loan_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active', db_column='loanstatus')
    released_by_id = models.ForeignKey(User, models.DO_NOTHING, db_column='releasedbyid')
    released_date = models.DateField(auto_now_add=True, db_column='releaseddate')

    def __str__(self):
        return f"Loan #{self.id} - {self.member}"


class LoanRepaymentSchedule(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Due', 'Due'),
        ('Overdue', 'Overdue'),
        ('Paid', 'Paid'),
    ]

    schedule_id = models.AutoField(primary_key=True, db_column='scheduleid')
    loan_id = models.ForeignKey(Loan, models.DO_NOTHING, db_column='loanid')
    due_date = models.DateField(db_column='duedate')
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, db_column='amountdue')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_column='status')
    paid_date = models.DateField(null=True, blank=True, db_column='paiddate')
    created_at = models.DateTimeField(auto_now_add=True, db_column='createdate')

    def __str__(self):
        return f"Schedule #{self.id} for Loan #{self.loan.id}"


class LoanPenalty(models.Model):
    penalty_id = models.AutoField(primary_key=True, db_column='penaltyid')
    schedule_id = models.ForeignKey(LoanRepaymentSchedule, models.DO_NOTHING, db_column='scheduleid')
    penalty_amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='penaltyamount')
    days_overdue = models.IntegerField(db_column='daysoverdue')
    date_evaluated = models.DateField(db_column='dateevaluated')

    def __str__(self):
        return f"Penalty #{self.id} for Schedule #{self.schedule.id}"
