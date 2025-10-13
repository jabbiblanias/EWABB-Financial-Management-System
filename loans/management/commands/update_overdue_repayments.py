from datetime import date
from loans.models import Loan, LoanRepaymentSchedule
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "update if there are overdues"

    def handle(self, *args, **options):
        updated = LoanRepaymentSchedule.objects.filter(
            due_date=date.today(),
            status='Pending'
        ).update(status='Due')
        self.stdout.write(self.style.SUCCESS(f'Updated {updated} repayment schedules'))