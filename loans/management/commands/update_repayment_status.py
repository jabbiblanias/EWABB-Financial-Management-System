from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from dateutil.relativedelta import relativedelta # 👈 Requires python-dateutil
from financial_reporting.models import Funds, Revenue
from loans.models import LoanRepaymentSchedule, LoanPenalty, Loan
from transactions.models import Transactions
from members.models import Savings
from notifications.models import Notification
from django.db.models import F
from django.utils.dateformat import DateFormat
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


MONTHLY_PENALTY_RATE = 0.02
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
            'loan_id',
        )

        for schedule in due_schedules:
            
            notification = Notification.objects.create(
                user_id=schedule.loan_id.member_id.user_id,
                title="Friendly Reminder: Loan Payment Due Today",
                message=(
                    f"Your loan payment (ID: {schedule.loan_id.pk}) is due today, "
                    f"{DateFormat(schedule.due_date).format('M d, Y')}. "
                    f"The amount due is **₱{schedule.amount_due:,.2f}**. "
                    f"Please ensure your payment is made promptly."
                )
            )

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "notifications",
                {
                    "type": "send_notification",
                    "payload": {
                        "id": notification.notification_id,
                        "message": notification.message,
                        "title": notification.title,
                        "date": timezone.localtime(notification.created_at).strftime('%b %d, %Y %I:%M %p'),
                        "is_read": notification.is_read,
                    }
                }
            )

        updated_overdue_bulk = LoanRepaymentSchedule.objects.filter(
            due_date__lt=today
        ).exclude(
            status__in=EXCLUDE_STATUSES
        ).update(status='Overdue')
        
        with transaction.atomic():
            schedules_for_penalty = (
                LoanRepaymentSchedule.objects
                .select_related("loan_id")
                .filter(
                    due_date__lt=today, 
                    status='Overdue',
                )
                .all()
            )

            for schedule in schedules_for_penalty:
                last_penalty = LoanPenalty.objects.filter(
                    schedule_id=schedule
                ).order_by('-date_evaluated').first()
                
                if last_penalty:
                    penalty_due_date = last_penalty.date_evaluated + relativedelta(months=+1)
                else:
                    penalty_due_date = schedule.due_date
                
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

                        Revenue.objects.create(
                            source='Savings Penalty Deduction',
                            amount=penalty_amount,
                            penalty_id=penalty
                        )

                        Funds.objects.filter(fund_name='Revenue').update(
                            balance=F('balance') + penalty_amount
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

                        notification = Notification.objects.create(
                            user_id=member.user_id,
                            title="Penalty Deducted from Savings",
                            message=(
                                f"A loan penalty has been deducted from your savings account. "
                                f"Due Date: {DateFormat(schedule.due_date).format('M d, Y')}. "
                                f"Penalty Amount: ₱{penalty_amount:,.2f}. "
                                f"Your updated savings balance is ₱{savings.balance:,.2f}."
                            )
                        )

                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            "notifications",
                            {
                                "type": "send_notification",
                                "payload": {
                                    "id": notification.notification_id,
                                    "message": notification.message,
                                    "title": notification.title,
                                    "date": timezone.localtime(notification.created_at).strftime('%b %d, %Y %I:%M %p'),
                                    "is_read": notification.is_read,
                                }
                            }
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

                        Revenue.objects.create(
                            source='Amount Due Penalty',
                            amount=penalty_amount,
                            penalty_id=penalty
                        )

                        Funds.objects.filter(fund_name='Revenue').update(
                            balance=F('balance') + penalty_amount
                        )

                        Transactions.objects.create(
                            member_id=member,
                            cashier_id=None, # System transaction
                            amount=penalty_amount,
                            transaction_type='Penalty Accrual', # 👈 Use 'Penalty Accrual'
                            loan_id=schedule.loan,
                            penalty_id=penalty
                        )

                        notification = Notification.objects.create(
                            user_id=member.user_id,
                            title="Penalty Added to Loan Due",
                            message=(
                                f"A penalty has been added to your loan repayment amount. "
                                f"Due Date: {DateFormat(schedule.due_date).format('M d, Y')}. "
                                f"Penalty Amount: ₱{penalty_amount:,.2f}. "
                                f"Your new total amount due is ₱{schedule.amount_due:,.2f}."
                            )
                        )

                        channel_layer = get_channel_layer()
                        async_to_sync(channel_layer.group_send)(
                            "notifications",
                            {
                                "type": "send_notification",
                                "payload": {
                                    "id": notification.notification_id,
                                    "message": notification.message,
                                    "title": notification.title,
                                    "date": timezone.localtime(notification.created_at).strftime('%b %d, %Y %I:%M %p'),
                                    "is_read": notification.is_read,
                                }
                            }
                        )

                    penalties_created_count += 1
                        
                updated_overdue_count += 1 

        self.stdout.write(self.style.SUCCESS(
            f'Updated {updated_due} schedules to Due.'
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Bulk-updated {updated_overdue_bulk} schedules to Overdue.'
        ))
        self.stdout.write(self.style.WARNING(
            f'Created {penalties_created_count} new monthly penalty records from {updated_overdue_count} schedules checked.'
        ))