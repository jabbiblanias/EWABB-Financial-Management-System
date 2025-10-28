from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from dateutil.relativedelta import relativedelta # 👈 Requires python-dateutil
from loans.models import LoanRepaymentSchedule, LoanPenalty, Loan
from transactions.models import Transactions
from members.models import Savings
from notifications.models import Notification
from django.db.models import F
from django.utils.dateformat import DateFormat


# Define constants
MONTHLY_PENALTY_RATE = 0.02 # Example: 2% monthly rate on the unpaid amount
EXCLUDE_STATUSES = ['Paid', 'Canceled']


class Command(BaseCommand):
    help = 'Updates loan repayment statuses either due or overdueand creates monthly penalties for overdue schedules.'

    def handle(self, *args, **options):
        today = timezone.localdate()
        penalties_created_count = 0
        updated_overdue_count = 0

        # --- 1. Bulk Update Schedules with DueDate == Today to 'Due' ---
        updated_due = LoanRepaymentSchedule.objects.filter(
            due_date=today
        ).exclude(
            status__in=EXCLUDE_STATUSES
        ).update(status='Due')

        due_schedules = LoanRepaymentSchedule.objects.filter(
            due_date=today,
            status='Due'
        ).select_related(
            'loan_id', # Optimize to fetch related objects (Loan, Member, User)
        )

        # --- 3. Iterate and create a notification for each schedule ---
        for schedule in due_schedules:
            # Ensure you have access to the necessary data (e.g., loan, member, user ID)
            
            Notification.objects.create(
                user_id=schedule.loan_id.member_id.user_id, # Assuming 'member' has a 'user' relationship
                title="Friendly Reminder: Loan Payment Due Today",
                message=(
                    f"Your loan payment (ID: {schedule.loan_id.pk}) is due today, "
                    f"{DateFormat(schedule.due_date).format('M d, Y')}. "
                    f"The amount due is **₱{schedule.amount_due:,.2f}**. "
                    f"Please ensure your payment is made promptly."
                )
            )

        # --- 2. Identify Schedules with DueDate < Today to 'Overdue' (Bulk Update for efficiency) ---
        # This flags *all* past-due, non-final schedules to Overdue in one query.
        updated_overdue_bulk = LoanRepaymentSchedule.objects.filter(
            due_date__lt=today
        ).exclude(
            status__in=EXCLUDE_STATUSES
        ).update(status='Overdue')
        
        # Note: We'll use a filtered set for penalties, as bulk update doesn't return objects.

        # --- 3. Identify and Process Schedules for Monthly Penalties (Iteration) ---
        with transaction.atomic():
            # Get the schedules that are now marked 'Overdue' or were already 'Overdue'
            # and need a penalty check. We exclude 'Paid' and 'Canceled' statuses.
            schedules_for_penalty = (
                LoanRepaymentSchedule.objects
                .select_related("loan_id")
                .filter(
                    due_date__lt=today, 
                    status='Overdue', # Only check already flagged 'Overdue'
                )
                .all()
            )

            for schedule in schedules_for_penalty:
                # Get the last penalty for this schedule
                last_penalty = LoanPenalty.objects.filter(
                    schedule_id=schedule
                ).order_by('-date_evaluated').first()
                
                # Determine the date for the next penalty check
                if last_penalty:
                    # Next penalty is due one month after the last penalty was *created*
                    penalty_due_date = last_penalty.date_evaluated + relativedelta(months=+1)
                else:
                    # If no previous penalty, next penalty is due one month after the original due date
                    penalty_due_date = schedule.due_date
                
                
                # A. Check if the monthly penalty is due
                is_penalty_due = (today >= penalty_due_date)

                if is_penalty_due:
                    
                    # --- CALCULATE MONTHLY PENALTY ---             
                    penalty_amount = schedule.amount_due * Decimal(MONTHLY_PENALTY_RATE)

                    member = schedule.loan_id.member_id
                    savings = Savings.objects.get(member_id=member)
                    
                    # 1. Create the new penalty record
                    if savings.balance >= penalty_amount:
                        savings.balance -= penalty_amount
                        savings.save()

                        penalty = (
                            LoanPenalty.objects.create(
                                schedule_id=schedule,
                                penalty_amount=penalty_amount,
                                penalty_type='Savings Penalty Deduction',
                                date_evaluated=today # The date the penalty was created
                            )
                        )

                        Transactions.objects.create(
                            member_id=member,
                            cashier_id=None, # System transaction, no physical cashier
                            amount=penalty_amount,
                            transaction_type='Penalty Deduction', # 👈 Use 'Penalty Deduction'
                            loan_id=schedule.loan,
                            penalty_id=penalty,
                            savings_id=savings
                        )

                        Notification.objects.create(
                            user_id=member.user_id,
                            title="Penalty Deducted from Savings",
                            message=(
                                f"A loan penalty has been deducted from your savings account. "
                                f"Due Date: {DateFormat(schedule.due_date).format('M d, Y')}. "
                                f"Penalty Amount: ₱{penalty_amount:,.2f}. "
                                f"Your updated savings balance is ₱{savings.balance:,.2f}."
                            )
                        )

                    else:
                        LoanRepaymentSchedule.objects.filter(pk=schedule.pk).update(
                            amount_due=F('amount_due') + penalty_amount
                        )
                        penalty = (
                            LoanPenalty.objects.create(
                                schedule_id=schedule,
                                penalty_amount=penalty_amount,
                                penalty_type='Amount Due Penalty Added',
                                date_evaluated=today # The date the penalty was created
                            )
                        )

                        # The Schedule object is 'schedule'
                        loan_pk = schedule.loan_id # Get the primary key of the related Loan

                        # Use F() to safely add the penalty_amount to the OutstandingBalance field in the database
                        Loan.objects.filter(pk=loan_pk).update(
                            remaining_balance=F('remaining_balance') + penalty_amount
                        )

                        Transactions.objects.create(
                            member_id=member,
                            cashier_id=None, # System transaction
                            amount=penalty_amount,
                            transaction_type='Penalty Accrual', # 👈 Use 'Penalty Accrual'
                            loan_id=schedule.loan,
                            penalty_id=penalty
                        )

                        Notification.objects.create(
                            user_id=member.user_id,
                            title="Penalty Added to Loan Due",
                            message=(
                                f"A penalty has been added to your loan repayment amount. "
                                f"Due Date: {DateFormat(schedule.due_date).format('M d, Y')}. "
                                f"Penalty Amount: ₱{penalty_amount:,.2f}. "
                                f"Your new total amount due is ₱{schedule.amount_due:,.2f}."
                            )
                        )

                    penalties_created_count += 1
                        
                # Count schedules processed for reporting
                updated_overdue_count += 1 


        # --- Report Results ---
        # Count schedules processed for reporting
        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_due} schedules to Due.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Bulk-updated {updated_overdue_bulk} schedules to Overdue.'
        ))
        self.stdout.write(self.style.WARNING(
            f'Created {penalties_created_count} new monthly penalty records from {updated_overdue_count} schedules checked.'
        ))