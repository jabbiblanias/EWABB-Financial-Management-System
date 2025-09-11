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
from members.models import Member
from django.utils import timezone
from notifications.models import Notification

@transaction.atomic
def transactions(request):
    try:
        if request.method == 'POST':
            cashier_id = request.user
            account_number = request.POST.get('accountNumber')
            amount = Decimal(request.POST.get('amount'))
            amount_received = Decimal(request.POST.get('amountReceived') or 0)
            transaction_type = request.POST.get('transactionType')

            member = Member.objects.get(account_number=account_number)

            #Change computation
            change = amount_received - amount

            if transaction_type == 'Savings Deposit':
                savings = Savings.objects.get(member_id=member)
                savings.balance += amount
                savings.save()
                message = f"Savings deposit of ₱{amount} from Account #{member.account_number} completed successfully."
            elif transaction_type == 'Loan Payment':
                loan = Loan.objects.filter(member_id=member, loan_status="Active").first()
                if not loan:
                    return JsonResponse({"success": False, "message": "This account number doesn't have active loan."})
                
                message, excess = record_payment(member, loan, amount)
                if excess != 0:
                    amount -= excess
                change += excess
            elif transaction_type == 'Withdrawal':
                amount_received = None
                change = None
                savings = Savings.objects.get(member_id=member)
                if savings.balance >= amount:
                    savings.balance -= amount
                    savings.save()
                    message = f"Withdrawal of ₱{amount} from Account #{member.account_number} processed successfully."
                else:
                    # Not enough balance
                    message = f"Account #{member.account_number} has insufficient balance!"

                    return JsonResponse({"success": False, "message": message})
                
            
            Transactions.objects.create(
                member_id=member,
                cashier_id=cashier_id,
                amount=amount,
                amount_received=amount_received,
                change=change,
                transaction_type=transaction_type
            )
            context = transaction_data()
            html = render_to_string('transactions/partials/cashier_transaction_table_body.html', context)
            return JsonResponse({"success": True, "message": message, "html": html})
    except IntegrityError as e:
        return JsonResponse({"success": False, "message": "Transaction failed. Please try again."})


def record_payment(member_id, loan, payment_amount):

    repayment = LoanRepaymentSchedule.objects.filter(
        loan_id=loan
    ).exclude(status='Paid').order_by('due_date').first()
    
    # Case: loan is already fully paid
    if not repayment:
        return f"Loan {loan.loan_id} is already fully paid. Excess: {payment_amount}", payment_amount

    # Case 1: full or over payment
    if payment_amount >= repayment.amount_due:
        remaining = payment_amount - repayment.amount_due
        # update repayment
        repayment.paid_amount = repayment.paid_amount + repayment.amount_due if repayment.paid_amount else repayment.amount_due
        repayment.amount_due = 0
        repayment.paid_date = timezone.now()
        repayment.last_updated = timezone.now()
        repayment.status = 'Paid'
        repayment.save()

        # update loan totals
        loan.total_paid = loan.total_paid + repayment.paid_amount if loan.total_paid else repayment.paid_amount
        loan.remaining_balance = max(0, loan.remaining_balance - repayment.paid_amount)
        loan.save()

        # ✅ Mark loan as Completed if fully paid
        if loan.remaining_balance == 0:
            loan.loan_status = "Completed"
            loan.save()

        # If there’s excess, apply it to the next repayment
        if remaining > 0:
            return record_payment(member_id, loan, remaining)
        else:
            return f"Payment recorded. due date {repayment.due_date} has been fully paid.", 0

    # Case 2: partial payment
    else:
        if repayment.status != "Overdue":
            repayment.status = 'Partially Paid'
        repayment.amount_due -= payment_amount
        repayment.paid_amount = repayment.paid_amount + payment_amount if repayment.paid_amount else payment_amount
        repayment.paid_date = timezone.now()
        repayment.last_updated = timezone.now()
        repayment.save()

        # update loan totals
        loan.total_paid = loan.total_paid + payment_amount if loan.total_paid else payment_amount
        loan.remaining_balance = max(0, loan.remaining_balance - payment_amount)
        loan.save()

    return f"Payment of ₱{payment_amount} from Account #{member_id.account_number} recorded successfully.",0


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
    members = (
        Member.objects
        .select_related("person_id")
        .values(
            "account_number",
            "person_id__first_name",
            "person_id__middle_name",
            "person_id__name_extension",
            "person_id__surname"
        )
    )
    context = {"transactions": transactions, "members": members}
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


def loan_balance(request):
    account_number = request.GET.get("accountNumber")

    # Check if member exists
    member = Member.objects.select_related("person_id").filter(account_number=account_number).first()
    if not member:
        return JsonResponse({"exists": False, "loan_balance": None})
    
    first_name = member.person_id.first_name
    middle_name = member.person_id.middle_name
    name_extension = member.person_id.name_extension
    last_name = member.person_id.surname
    member_name = ", ".join(
        part for part in [last_name, first_name, middle_name, name_extension] if part
    )


    # Get loan for this member
    loan = Loan.objects.filter(member_id=member).exclude(loan_status="Completed").first()
    if not loan:
        return JsonResponse({"exists": True, "member_name": member_name})

    return JsonResponse({"exists": True, "member_name": member_name, "loan_balance": loan.remaining_balance})