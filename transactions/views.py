from django.shortcuts import render
from django.db import connection, transaction, IntegrityError
from loans.models import Loan, LoanRepaymentSchedule, LoanPenalty
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date
from .models import Transactions, Member
from members.models import Savings
from datetime import datetime
from django.db.models import Sum
from django.http import JsonResponse, HttpResponseForbidden
from decimal import Decimal
from django.template.loader import render_to_string
from members.models import Member
from programs.models import BusinessProgram
from django.utils import timezone
from notifications.models import Notification
from django.core.paginator import Paginator 
from django.utils.dateformat import DateFormat

@transaction.atomic
def transactions(request):
    try:
        if request.method == 'POST':
            cashier_id = request.user
            account_number = request.POST.get('accountNumber')
            amount = Decimal(request.POST.get('amount'))
            amount_received = Decimal(request.POST.get('amountReceived') or 0)
            transaction_type = request.POST.get('transactionType')
            program_id = request.POST.get('programType') or None

            member = Member.objects.get(account_number=account_number)

            #Change computation
            change = amount_received - amount

            if transaction_type == 'Savings Deposit':
                savings = Savings.objects.get(member_id=member)
                savings.balance += amount
                savings.save()
                toast_message = f"Savings deposit of ₱{amount} from Account #{member.account_number} completed successfully."

                # 🔔 Member notification (different wording)
                Notification.objects.create(
                    user_id=member.user_id,
                    title="Savings Deposit",
                    message=(
                        f"You deposited ₱{amount:,} into your savings account on "
                        f"{timezone.now().strftime('%b %d, %Y %I:%M %p')}. "
                        f"Your new balance is ₱{savings.balance:,}."
                    )
                )
                transaction_id = Transactions.objects.create(
                    member_id=member,
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    savings_id=savings
                )
            elif transaction_type == 'Loan Payment':
                loan = Loan.objects.filter(member_id=member, loan_status="Active").first()
                if not loan:
                    return JsonResponse({"success": False, "message": "This account number doesn't have active loan."})
                
                toast_message, excess = record_payment(member, loan, amount)
                if excess != 0:
                    amount -= excess
                change += excess
                transaction_id = Transactions.objects.create(
                    member_id=member,
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    loan_id=loan
                )
            elif transaction_type == 'Withdrawal':
                amount_received = None
                change = None
                savings = Savings.objects.get(member_id=member)
                if savings.balance >= amount:
                    savings.balance -= amount
                    savings.save()
                    toast_message = f"Withdrawal of ₱{amount} from Account #{member.account_number} processed successfully."

                    # 🔔 Member notification (different wording)
                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Withdrawal",
                        message=(
                            f"You withdrew ₱{amount:,} from your savings account on "
                            f"{timezone.now().strftime('%b %d, %Y %I:%M %p')}. "
                            f"Remaining balance: ₱{savings.balance:,}."
                        )
                    )
                    transaction_id = Transactions.objects.create(
                        member_id=member,
                        cashier_id=cashier_id,
                        amount=amount,
                        amount_received=amount_received,
                        change=change,
                        transaction_type=transaction_type,
                        savings_id=savings
                    )
                else:
                    # Not enough balance
                    toast_message = f"Account #{member.account_number} has insufficient balance!"

                    return JsonResponse({"success": False, "message": toast_message})
            elif transaction_type == 'Program Deposit':
                program = BusinessProgram.objects.get(program_id=program_id)
                program.total_profit += amount
                program.save()
                toast_message = f"Program '{program.program_name}' deposit of ₱{amount} from Account #{member.account_number} completed successfully."

                # 🔔 Member notification (different wording)
                Notification.objects.create(
                    user_id=member.user_id,
                    title="Program Deposit",
                    message=(
                        f"You deposited ₱{amount:,} into {program.program_name} on "
                        f"{timezone.now().strftime('%b %d, %Y %I:%M %p')}."
                    )
                )

                transaction_id = Transactions.objects.create(
                    member_id=member,
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    program_id=program
                )
            person_id = member.person_id
            transaction = {
                "transaction_id": transaction_id.transaction_id,
                "transaction_type": transaction_id.transaction_type,
                "account_number": transaction_id.member_id.account_number,
                "member_name": f"{person_id.first_name} {person_id.surname}",
                "transaction_date": DateFormat(transaction_id.transaction_date).format("Y-m-d H:i A"),
                "amount_received": f"{transaction_id.amount_received or 0:.2f}",
                "amount": f"{transaction_id.amount or 0:.2f}",
                "change": f"{transaction_id.change or 0:.2f}",
            }
            print(transaction)
            context = transaction_data(request, ajax=True, transaction=transaction, toast_message=toast_message)
            return context
    except IntegrityError as e:
        return JsonResponse({"success": False, "message": "Transaction failed. Please try again."})

@transaction.atomic
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
            Notification.objects.create(
                user_id=member_id.user_id,
                title="Loan Fully Paid",
                message=f"Your due on {repayment.due_date.strftime('%b %d, %Y')} has been paid. Congratulations, your loan is fully paid!"
            )
        else:
            # Next due
            next_due = LoanRepaymentSchedule.objects.filter(loan_id=loan, status__in=['Pending','Partially Paid']).order_by('due_date').first()
            note = f"Your due on {repayment.due_date.strftime('%b %d, %Y')} has been paid."
            if next_due:
                note += f" Next due: {next_due.due_date.strftime('%b %d, %Y')} amount ₱{next_due.amount_due:,}."
            Notification.objects.create(
                user_id=member_id.user_id,
                title="Loan Due Paid",
                message=note
            )

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

        # 🔔 Create partial payment notification
        Notification.objects.create(
            user_id=member_id.user_id,
            title="Partial Loan Payment",
            message=f"Payment of ₱{payment_amount:,} recorded for due {repayment.due_date.strftime('%b %d, %Y')}. Remaining due: ₱{repayment.amount_due:,}."
        )

    return f"Payment of ₱{payment_amount} from Account #{member_id.account_number} recorded successfully.", 0


def transaction_view(request):
    user = request.user

    # detect ajax once here
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    # get shared data
    context = transaction_data(request, ajax=is_ajax)

    # if ajax, just return the JSON
    if is_ajax:
        return context  # this is your JsonResponse
    
    # otherwise, render template normally
    if user.groups.filter(name='Admin').exists():
        return render(request, 'transactions/admin_transaction.html', context)
    elif user.groups.filter(name='Member').exists():
        return member_transaction_data(request)
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'transactions/bookkeeper_transaction.html', context)
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'transactions/cashier_transaction.html', context)
    else:
        return HttpResponseForbidden("Unauthorized user group.")
    
def transaction_data(request, ajax=False, transaction=None, toast_message=None):
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
    programs = (
        BusinessProgram.objects
        .filter(status="Active")
        .values('program_id', 'program_name')
        )
    
    paginator = Paginator(transactions, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    
    if ajax:
        html = render_to_string("transactions/partials/cashier_transaction_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True, "message": toast_message, "table_body_html": html, "pagination_html": pagination, "transaction": transaction})
    
    context = {"members": members, "programs": programs, "page": page}
    return context


def member_transaction_data(request):
    user = request.user
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
    
    paginator = Paginator(transactions, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    context = {"transactions": transactions, "page": page}
    
    if is_ajax:
        html = render_to_string("transactions/partials/member_transaction_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})
    
    return render(request, 'transactions/member_transaction.html', context)


def balance(request):
    account_number = request.GET.get("accountNumber")
    transaction_type = request.GET.get("transactionType")


    # Check if member exists
    member = Member.objects.select_related("person_id").filter(account_number=account_number).first()
    if not member:
        return JsonResponse({"exists": False, "balance": None})
    
    first_name = member.person_id.first_name
    middle_name = member.person_id.middle_name
    name_extension = member.person_id.name_extension
    last_name = member.person_id.surname
    member_name = ", ".join(
        part for part in [last_name, first_name, middle_name, name_extension] if part
    )

    if transaction_type == "Savings Deposit" or transaction_type == "Withdrawal":
        savings = Savings.objects.filter(member_id=member).first()
        if not savings:
            return JsonResponse({"exists": True, "member_name": member_name})
        balance = savings.balance
    elif transaction_type == "Loan Payment":
        # Get loan for this member
        loan = Loan.objects.filter(member_id=member, loan_status="Active").first()
        if not loan:
            return JsonResponse({"exists": True, "member_name": member_name})
        balance = loan.remaining_balance
    else:
        return JsonResponse({"exists": True, "member_name": member_name})
    return JsonResponse({"exists": True, "member_name": member_name, "balance": balance})

def passbook_print(request):
    return render(request, 'transactions/partials/passbook.html')