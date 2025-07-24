from django.shortcuts import render
from django.db import connection, transaction
from loans.models import LoanApplication, Loan, LoanRepaymentSchedule
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date


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
    years = loan_application.loan_term_years
    months = loan_application.loan_term_months
    days = loan_application.loan_term_days
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