from django.utils import timezone
from loans.models import Loan, LoanRepaymentSchedule
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        today = timezone.localdate()
        updated_due = LoanRepaymentSchedule.objects.filter(
            due_date=today
        ).update(status='Due')

        updated_overdue = LoanRepaymentSchedule.objects.filter(
            due_date__lt=today
        ).update(status='Overdue')

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_due} schedules to Due and {updated_overdue} to Overdue.'
        ))