from datetime import date
from loans.models import Loan, LoanRepaymentSchedule
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "update loan status"

    def handle(self, *args, **options):
        updated = LoanRepaymentSchedule.objects.filter(
            due_date=date.today()
        ).update(status='Due')

        updated = LoanRepaymentSchedule.objects.filter(
            due_date__lt=date.today()
        ).update(status='Overdue')