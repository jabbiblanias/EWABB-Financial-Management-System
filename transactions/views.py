from django.shortcuts import render
from django.db import connection, transaction
from loans.models import LoanApplication, Loan, LoanRepaymentSchedule, LoanPenalty
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date
from .models import Savings, Transactions, Member
from datetime import date
from django.db.models import Sum


def loan_release(request):
    if request.method == 'POST':
        user = request.user
        loan_application_id = request.POST.get('applicationid')

        loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)
        loan = Loan.objects.create(
            loan_application_id=loan_application,
            member_id=loan_application.member_id,
            outstanding_balance=loan_application.total_payable,
            released_by_id=user,
        )

        create_loan_repayment_schedule(loan_application, loan)
        
def create_loan_repayment_schedule(loan_application, loan):
    years = loan_application.loan_term_years or 0
    months = loan_application.loan_term_months or 0
    days = loan_application.loan_term_days or 0
    amount_due = loan_application.monthly_amortization
    released_date = loan.released_date
    
    loan_term = relativedelta(years=years, months=months, days=days)
    due_date = released_date + loan_term
    total_days = convert_date(years, months, days)
    
    LoanRepaymentSchedule.objects.create(
            loan_id=loan,
            due_date=due_date,
            amount_due=amount_due
        )
    
    new_due_date = due_date
    remaining_days = total_days
    if total_days != 100:
        while remaining_days != 0:
            new_due_date += relativedelta(days=30)

            LoanRepaymentSchedule.objects.create(
                loan_id=loan,
                due_date=new_due_date,
                amount_due=amount_due
            )
            loan_term_to_days -= 30

            
@transaction.atomic
def transactions(request):
    if request.method == 'POST':
        cashier_id = request.user
        account_number = request.POST.get('accountNumber')
        amount = request.POST.get('amount')
        transaction_type = request.POST.get('transactionType')

        members = Member.objects.get(account_number=account_number)

        Transactions.objects.create(
            member_id=members,
            cashier_id=cashier_id,
            amount=amount,
            transaction_type=transaction_type
        )

        if transaction_type == 'Savings Deposit':
            savings = Savings.objects.get(member_id=members)
            savings += amount
            savings.save()
        elif transaction_type == 'Loan Payment':
            loan = Loan.objects.get(member_id=members)
            loan_repayment_schedule = LoanRepaymentSchedule.objects.get(loan_id=loan)
            if loan_repayment_schedule.status == 'Overdue':
                loan_repayment_schedules = LoanRepaymentSchedule.objects.filter(loan_id=loan).order_by('duedate')
                loan_penalty = LoanPenalty.objects.values('scheduleid').annotate(totalPenalty=Sum('penaltyamount'))
                total_loan_amount = loan_penalty

            loan_repayment_schedule.paid_date = date.today()
            if loan_repayment_schedule.amount_due == amount:
                loan_repayment_schedule.status = 'Paid'
            else:
                loan_repayment_schedule.status = 'Paid Partially'
        elif transaction_type == 'Withdrawal':
            savings = Savings.objects.get(member_id=members)
            if savings.amount >= amount:
                savings -= amount
                savings.save()

            