from django.shortcuts import render
from django.db import connection, transaction, IntegrityError
from loans.models import Loan, LoanRepaymentSchedule, LoanPenalty
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date
from .models import Transactions, Member
from members.models import Savings
from datetime import date
from django.db.models import Sum
from django.http import JsonResponse
from decimal import Decimal
from django.template.loader import render_to_string


@transaction.atomic
def transactions(request):
    try:
        if request.method == 'POST':
            cashier_id = request.user
            account_number = request.POST.get('accountNumber')
            amount = Decimal(request.POST.get('amount'))
            transaction_type = request.POST.get('transactionType')
            print(account_number)

            member = Member.objects.get(account_number=account_number)

            Transactions.objects.create(
                member_id=member,
                cashier_id=cashier_id,
                amount=amount,
                transaction_type=transaction_type
            )

            if transaction_type == 'Savings Deposit':
                savings = Savings.objects.get(member_id=member)
                savings.balance += amount
                savings.save()
                message = f"Savings deposit of ₱{amount} from Account #{member.account_number} completed successfully."
            elif transaction_type == 'Loan Payment':
                loan = Loan.objects.get(member_id=member)
                loan_repayment_schedule = LoanRepaymentSchedule.objects.get(loan_id=loan)
                if loan_repayment_schedule.status == 'Overdue':
                    loan_repayment_schedules = LoanRepaymentSchedule.objects.filter(loan_id=loan).order_by('duedate')
                    loan_penalty = LoanPenalty.objects.values('scheduleid').annotate(totalPenalty=Sum('penaltyamount'))
                    total_loan_amount = loan_penalty
                if loan_repayment_schedule.amount_due == amount:
                    loan_repayment_schedule.status = 'Paid'
                else:
                    loan_repayment_schedule.status = 'Paid Partially'
                loan_repayment_schedule.paid_date = date.today()
                message = f"Payment of ₱{amount} from Account #{member.account_number} recorded successfully."
            elif transaction_type == 'Withdrawal':
                savings = Savings.objects.get(member_id=member)
                if savings.balance >= amount:
                    savings.balance -= amount
                    savings.save()
                    message = f"Withdrawal of ₱{amount} from Account #{member.account_number} processed successfully."
            context = transaction_data()
            html = render_to_string('transactions/partials/cashier_transaction_table_body.html', context)
            return JsonResponse({"success": True, "message": message, "html": html})
    except IntegrityError as e:
        return JsonResponse({"success": False, "message": "Transaction failed. Please try again."})


def record_payment(loan_id, payment_amount):
    # get the earliest unpaid repayment for this loan
    repayment = LoanRepaymentSchedule.objects.filter(
        loan_id=loan_id
    ).exclude(status='Paid').order_by('due_date').first()

    if not repayment:
        return "Loan already fully paid"

    # Case 1: full payment
    if payment_amount >= repayment.amount_due:
        repayment.status = 'Paid'
        repayment.save()
        remaining = payment_amount - repayment.amount_due

        # If there’s excess, apply it to the next repayment
        if remaining > 0:
            record_payment(loan_id, remaining)

    # Case 2: partial payment
    else:
        repayment.amount_due -= payment_amount
        repayment.status = 'Partially Paid'
        repayment.save()


def transaction_view(request):
    user = request.user
    if user.groups.filter(name='Admin').exists():
        return render(request, 'transactions/admin_transaction.html')
    elif user.groups.filter(name='Member').exists():
        context = member_transaction_data(user)
        return render(request, 'transactions/member_transaction.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        context = transaction_data()
        return render(request, 'transactions/bookkeeper_transaction.html', context)
    elif user.groups.filter(name='Cashier').exists():
        context = transaction_data()
        return render(request, 'transactions/cashier_transaction.html', context)
    
def transaction_data():
    transactions = (
        Transactions.objects
        .select_related("member_id")
        .values(
            "transaction_id", 
            "transaction_type", 
            "member_id__account_number", 
            "transaction_date", 
            "amount"
        )
        .order_by("-transaction_date")
    )
    context = {"transactions": transactions}
    return context


def member_transaction_data(user):
    transactions = (
        Transactions.objects
        .select_related("member_id")
        .filter(member_id__user_id=user)  # filter only this user's transactions
        .values(
            "transaction_id", 
            "transaction_type",  
            "transaction_date", 
            "amount"
        )
        .order_by("-transaction_date")
    )
    context = {"transactions": transactions}
    return context
