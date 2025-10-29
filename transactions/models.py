from django.db import models
from django.contrib.auth.models import User
from members.models import Member, Savings
from loans.models import LoanRepaymentSchedule, LoanPenalty, Loan
from programs.models import BusinessProgram


class Transactions(models.Model):
    TRANSACTION_TYPES = [
        ('Loan Payment', 'Loan Payment'),
        ('Savings Deposit', 'Savings Deposit'),
        ('Withdrawal', 'Withdrawal'),
        ('Penalty Deduction', 'Penalty Deduction'), 
        ('Penalty Accrual', 'Penalty Accrual'),
    ]

    transaction_id = models.AutoField(primary_key=True, db_column='transactionid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, null=True, blank=True, db_column='memberid')
    cashier_id = models.ForeignKey(User, models.DO_NOTHING, null=True, blank=True , db_column='cashierid')
    amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='amount')
    amount_received = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, db_column='amountreceived')
    change = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES, db_column='transactiontype')
    transaction_date = models.DateTimeField(auto_now_add=True, db_column='createdAt')
    description = models.TextField(null=True, blank=True, db_column='description')
    savings_id = models.ForeignKey(Savings, models.DO_NOTHING, db_column='savings_id')
    loan_id = models.ForeignKey(Loan, models.DO_NOTHING, null=True, blank=True, db_column='loan_id')
    penalty_id = models.ForeignKey(LoanPenalty, models.DO_NOTHING, null=True, blank=True, db_column='penalty_id')
    program_id = models.ForeignKey(BusinessProgram, models.DO_NOTHING, null=True, blank=True, db_column='program_id')

    def __str__(self):
        return f"{self.transaction_type} by {self.member} on {self.date.strftime('%Y-%m-%d')}"
    
    class Meta:
        managed = False
        db_table = 'transactions'

class LoanPaymentBreakdown(models.Model):
    repayment = models.ForeignKey(LoanRepaymentSchedule, on_delete=models.CASCADE)
    transaction = models.ForeignKey(Transactions, on_delete=models.CASCADE, null=True, blank=True)
    principal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    interest = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    insurance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cbu = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    penalty = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_recorded = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Breakdown for {self.repayment.loan_id.loan_id} — ₱{self.total_payment}"
    
    class Meta:
        managed = False
        db_table = 'loan_payment_breakdown'