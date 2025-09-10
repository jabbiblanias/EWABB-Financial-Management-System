from celery import shared_task
from datetime import date
from .models import Loan
from .models import LoanRepaymentSchedule


@shared_task
def update_due_repayments():
    updated = LoanRepaymentSchedule.objects.filter(
        due_date=date.today(),
        status='Pending'
    ).update(status='Due')
    return f"Updated {updated} repayment schedules"


@shared_task
def update_overdue_repayments():
    updated = LoanRepaymentSchedule.objects.filter(
        due_date__lt=date.today(),
        status='Due'
    ).update(status='Overdue')
    return f"Updated {updated} repayment schedules"