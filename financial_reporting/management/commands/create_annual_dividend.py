from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.db.models import F
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from financial_reporting.models import Dividend, Financialreports, Memberfinancialdata
from members.models import Member, Savings
from transactions.models import Transactions
from financial_reporting.models import Funds
from notifications.models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.http import JsonResponse
from django.db.models import Subquery, OuterRef, Value, DecimalField, Case, When, Sum
from django.db.models.functions import Coalesce, Round
from loans.models import Loan, LoanRepaymentSchedule, LoanPenalty
from datetime import timedelta




class Command(BaseCommand):
    help = 'Create automatic backup based on frequency.'

    def handle(self, *args, **options):
        today = timezone.localdate()

        # 1️⃣ Find the last dividend date range
        last_dividend = Dividend.objects.order_by('-period_end').first()

        if last_dividend:
            period_start = last_dividend.period_end + timedelta(days=1)
        else:
            # First ever dividend → start from start of the year
            period_start = date(date.today().year, 1, 1)

        # 2️⃣ Define the new period end (up to today)
        current_date = date.today()

        period_end = current_date

        total_savings = Savings.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')

        # 3️⃣ Get revenues & expenses within this new period
        total_income = Funds.objects.filter(fund_name='Revenue').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
        total_expenses = Funds.objects.filter(fund_name='Expenses').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')

        net_surplus = total_income + total_expenses
        
        rate = (Decimal(net_surplus) / Decimal(total_savings)).quantize(Decimal('0.0001'))
        rate_percentage = (rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        # Subquery: latest loan release date per member
        latest_loan_date = Loan.objects.filter(
            member_id=OuterRef('pk'), loan_status="Active"
        ).order_by('-released_date').values('released_date')[:1]

        # Subquery: latest overdue schedule id per member's active loan
        latest_overdue_schedule = LoanRepaymentSchedule.objects.filter(
            loan_id__member_id=OuterRef('pk'),
            status='Overdue'
        ).order_by('-schedule_id').values('schedule_id')[:1]

        # Subquery: latest penalty amount per schedule
        latest_penalty_amount = LoanPenalty.objects.filter(
            schedule_id__loan_id__member_id=OuterRef('pk'), schedule_id__status='Overdue'
        ).order_by('-date_evaluated').values('penalty_amount')[:1]

        # Subquery: latest penalty date per schedule
        '''latest_penalty_date = LoanPenalty.objects.filter(
            schedule_id__loan_id__member_id=OuterRef('pk')
        ).order_by('-date_evaluated').values('date_evaluated')[:1]'''

        # Subquery: active loan balance
        active_loan_balance = Loan.objects.filter(
            member_id=OuterRef('pk'),
            loan_status='Active'
        ).values('remaining_balance')[:1]

        # Main Query
        financial_report = Member.objects.select_related("person_id").annotate(
            loan_balance=Coalesce(
                Subquery(active_loan_balance),
                Value(0),
                output_field=DecimalField()
            ),
            released_date=Subquery(latest_loan_date),
            savings_balance=Coalesce(
                Subquery(
                    Savings.objects.filter(member_id=OuterRef('pk')).values('balance')[:1]
                ),
                Value(0),
                output_field=DecimalField()
            ),
            schedule_id=Subquery(latest_overdue_schedule),
            penalty_amount=Subquery(latest_penalty_amount),
            #penalty_date=Subquery(latest_penalty_date),
        ).annotate(
            # Adjusted savings balance (savings + penalty if exists)
            savings_balance_with_penalty=Case(
                When(penalty_amount__isnull=False,
                    then=F('savings_balance') + F('penalty_amount')),
                default=F('savings_balance'),
                output_field=DecimalField()
            ),
            # Savings after deduction = original savings 
            savings_after_deduction=F('savings_balance'),
            total_savings_investment=F('savings_balance'),
            dividend_amount=Round(F('savings_balance') * rate, 2),
            updated_savings_investment=Round(F('savings_balance') + F('savings_balance') * rate, 2)
        ).order_by('member_id')


        with transaction.atomic():
            current_year = timezone.localdate().year
            if Dividend.objects.filter(period_end__year=current_year).exists():
                self.stdout.write(self.style.WARNING(f"Dividend for the current year ({current_year}) has already been processed. Aborting."))
                return # Correctly stop execution
            
            dividend = Dividend.objects.create(
                period_start=period_start,
                period_end=period_end,
                total_surplus=net_surplus,
                rate=rate,
            )

            # 6️⃣ Distribute to members
            members = Member.objects.all()
            total_distributed = Decimal('0.00')

            for member in members:
                savings = Savings.objects.filter(member_id=member).first()
                if not savings or savings.balance <= 0:
                    continue

                # Compute dividend
                dividend_amount = (savings.balance * Decimal(rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                # 3️⃣ Credit dividend to member’s savings
                Savings.objects.filter(pk=savings.pk).update(balance=F('balance') + dividend_amount)
                total_distributed += dividend_amount

                # 4️⃣ Record a transaction entry for transparency
                Transactions.objects.create(
                    member_id=member,
                    transaction_type='Dividend Credit',
                    amount=dividend_amount,
                    transaction_date=date.today(),
                    savings_id=savings
                )

                notification = Notification.objects.create(
                    member=member,
                    title="Dividend Credit",
                    message=f"You received ₱{dividend_amount:.2f} as your dividend for the Fiscal Year "
                            f"{current_year}.",
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

            # Deduct total from Revenue fund once (after all members)
            revenue = Funds.objects.filter(fund_name='Revenue').first()
            if revenue:
                revenue.balance = Decimal('0.00')
                revenue.save(update_fields=['balance'])

            remains_from_net_surplus = net_surplus - total_distributed

            # If you want to clear Expenses fund (optional)
            expenses = Funds.objects.filter(fund_name='Expenses').first()
            if expenses:
                expenses.balance = remains_from_net_surplus  # or handle differently
                expenses.save(update_fields=['balance'])

            report = Financialreports.objects.create(report_type="dividend", dividend_id=dividend)

            for data in financial_report:
                Memberfinancialdata.objects.create(
                    financial_report=report,
                    account_number=data.account_number,
                    name=f"{data.person_id.first_name} {data.person_id.surname}",
                    loan_balance=data.loan_balance,
                    released_date=data.released_date,
                    savings_balance=data.savings_balance,
                    schedule_id=data.schedule_id,
                    penalty_amount=data.penalty_amount,
                    #penalty_date=data.penalty_date,
                    savings_balance_with_penalty=data.savings_balance_with_penalty,
                    savings_after_deduction=data.savings_after_deduction,
                    total_savings_investment=data.total_savings_investment,
                    dividend_amount=data.dividend_amount,
                    updated_savings_investment=data.updated_savings_investment,
                )

        self.stdout.write(self.style.SUCCESS('Successfully created annual dividend report.'))
