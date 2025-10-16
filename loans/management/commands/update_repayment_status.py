from django.utils import timezone
from loans.models import Loan, LoanRepaymentSchedule
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        today = timezone.localdate()
        EXCLUDE_STATUSES = ['Paid', 'Canceled']
        
        updated_due = LoanRepaymentSchedule.objects.filter(
            due_date=today
        ).exclude(
            status__in=EXCLUDE_STATUSES
        ).update(status='Due')

        updated_overdue = LoanRepaymentSchedule.objects.filter(
            due_date__lt=today
        ).exclude(
            status__in=EXCLUDE_STATUSES
        ).update(status='Overdue')

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_due} schedules to Due and {updated_overdue} to Overdue.'
        ))