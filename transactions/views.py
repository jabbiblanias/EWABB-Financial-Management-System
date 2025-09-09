from django.shortcuts import render
from django.db import connection, transaction, IntegrityError
from loans.models import Loan, LoanRepaymentSchedule, LoanPenalty
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date
from .models import Transactions, Member
from members.models import Savings
from datetime import datetime
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
                record_payment(member, amount)
                message = None
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


def record_payment(member_id, payment_amount):
    loan = Loan.objects.filter(member_id=member_id, loan_status="Active").first()

    if not loan:
        return JsonResponse({"message": "This account number doesn't have active loan."})

    repayment = LoanRepaymentSchedule.objects.filter(
        loan_id=loan
    ).exclude(status='Paid').order_by('due_date').first()
    
    # Case: loan is already fully paid
    if not repayment:
        return JsonResponse({"message": f"Loan {loan.loan_id} is already fully paid. Excess: {payment_amount}" if payment_amount > 0 else "Loan already fully paid"})

    # Case 1: full or over payment
    if payment_amount >= repayment.amount_due:
        remaining = payment_amount - repayment.amount_due

        # update repayment
        repayment.paid_amount = repayment.paid_amount + repayment.amount_due if repayment.paid_amount else repayment.amount_due
        repayment.amount_due = 0
        repayment.paid_date = datetime.today()
        repayment.last_updated = datetime.today()
        repayment.status = 'Paid'
        repayment.save()

        # update loan totals
        loan.total_paid = loan.total_paid + repayment.paid_amount if loan.total_paid else repayment.paid_amount
        loan.remaining_balance = max(0, loan.remaining_balance - repayment.paid_amount)
        loan.save()

        # If there’s excess, apply it to the next repayment
        if remaining > 0:
            return record_payment(member_id, remaining)
        else:
            return JsonResponse({"message": f"Payment recorded. due date {repayment.due_date} has been fully paid."})

    # Case 2: partial payment
    else:
        if repayment.status != "Overdue":
            repayment.status = 'Partially Paid'
        repayment.amount_due -= payment_amount
        repayment.paid_amount = repayment.paid_amount + payment_amount if repayment.paid_amount else payment_amount
        repayment.paid_date = datetime.today()
        repayment.last_updated = datetime.today()
        repayment.save()

        # update loan totals
        loan.total_paid = loan.total_paid + payment_amount if loan.total_paid else payment_amount
        loan.remaining_balance = max(0, loan.remaining_balance - payment_amount)
        loan.save()

    return JsonResponse({"message": f"Payment of ₱{payment_amount} from Account #{member_id.account_number} recorded successfully."})


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
