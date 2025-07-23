from django.db import models
from django.contrib.auth.models import User
from members.models import Member

class Savings(models.Model):
    savings_id = models.AutoField(primary_key=True, db_column='savingsid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='amount')

    def __str__(self):
        return f"Savings #{self.id} - Member: {self.member}"

class Transactions(models.Model):
    TRANSACTION_TYPES = [
        ('Loan Payment', 'Loan Payment'),
        ('Savings Deposit', 'Savings Deposit'),
        ('Withdrawal', 'Withdrawal'),
        ('Loan Release ', 'Loan Release'),
    ]

    transaction_id = models.AutoField(primary_key=True, db_column='transactionid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    cashier_id = models.ForeignKey(User, models.DO_NOTHING, related_name='cashier_transactions', db_column='cashierid')
    amount = models.DecimalField(max_digits=12, decimal_places=2, db_column='amount')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES, db_column='transactiontype')
    transaction_date = models.DateTimeField(auto_now_add=True, db_column='date')

    def __str__(self):
        return f"{self.transaction_type} by {self.member} on {self.date.strftime('%Y-%m-%d')}"