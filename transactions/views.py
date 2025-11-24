from django.shortcuts import render
from django.db import connection, transaction, IntegrityError
from loans.models import Loan, LoanRepaymentSchedule, LoanPenalty
from dateutil.relativedelta import relativedelta
from loans.utils import convert_date
from .models import Transactions, Member
from members.models import Savings
from datetime import datetime, timedelta
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
from itertools import chain
from decimal import Decimal, InvalidOperation # Import Decimal and related tools
from financial_reporting.models import Revenue, Funds
from django.db.models import F, Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def member_details(request, member_id):
    # Fetch member
    member = Member.objects.select_related('person_id').get(member_id=member_id)

    # 1. Fetch Data (ordered ascending for calculation)
    # Note: Use 'pk' or 'id' as a secondary sort key for transactions on the same date.
    savings_transactions = Transactions.objects.filter(
        member_id=member,
        transaction_type__in=['Savings Deposit', 'Withdrawal', 'Dividend Credit']
    ).order_by('transaction_date', 'pk')

    loan_transactions = Transactions.objects.filter(
        member_id=member,
        transaction_type__in=['Loan Payment', 'Loan Release']
    ).select_related('loan_id__loan_application_id').order_by('transaction_date', 'pk')

    # 2. Initialize Starting Balances
    current_savings_balance = Decimal('0.00')
    current_loan_balance = Decimal('0.00')

    # 3. Calculate Running Savings Balance (CBU)
    for t in savings_transactions:
        try:
            # Ensure amount is a Decimal
            amount = t.amount if t.amount is not None else Decimal('0.00')
        except InvalidOperation:
            amount = Decimal('0.00') 

        if t.transaction_type in ['Savings Deposit', 'Dividend Credit']:
            current_savings_balance += amount
        elif t.transaction_type == 'Withdrawal':
            current_savings_balance -= amount
            
        t.savings_balance = current_savings_balance

    # 4. Calculate Running Loan Balance
    for t in loan_transactions:
        try:
            # Ensure amount is a Decimal
            amount = t.amount if t.amount is not None else Decimal('0.00')
        except InvalidOperation:
            amount = Decimal('0.00')
        
        if t.transaction_type == 'Loan Release':
            current_loan_balance += t.loan_id.loan_application_id.total_payable
        elif t.transaction_type == 'Loan Payment':
            current_loan_balance -= amount
            
        t.loan_balance = current_loan_balance

    # 5. Combine and Prepare for Template
    all_transactions = list(chain(savings_transactions, loan_transactions))
    
    # *** FIX FOR ASCENDING ORDER (OLDEST AT TOP) ***
    # By removing reverse=True, the transactions are sorted oldest-to-newest.
    all_transactions.sort(key=lambda t: t.transaction_date) 

    context = {
        'member': member,
        'transactions': all_transactions,
    }
    
    return render(request, 'transactions/member_ledger.html', context)

@transaction.atomic
def transactions(request):
    try:
        if request.method == 'POST':
            cashier_id = request.user
            account_number = request.POST.get('accountNumber') or None
            amount = Decimal(request.POST.get('amount'))
            amount_received = Decimal(request.POST.get('amountReceived') or 0)
            transaction_type = request.POST.get('transactionType')
            program_id = request.POST.get('programType') or None
            description = request.POST.get('description') or None

            member = None 

            member_required_types = ['Savings Deposit', 'Loan Payment', 'Withdrawal']

            # 2. Perform Member Validation and Member-Specific Duplicate Check
            if transaction_type in member_required_types:
                if not account_number:
                    return JsonResponse({'success': False, 'message': 'Account number is required for this transaction type.'})
                
                # Fetch and lock the member record
                member = Member.objects.select_for_update().filter(account_number=account_number).first()
                if not member:
                    return JsonResponse({'success': False, 'message': 'Invalid account number.'})
                
                # 🧠 Check for recent duplicate transaction (Member-specific)
                recent_time_limit = timezone.now() - timedelta(seconds=5)
                if Transactions.objects.filter(
                    member_id=member,
                    transaction_type=transaction_type,
                    amount=amount,
                    transaction_date__gte=recent_time_limit
                ).exists():
                    return JsonResponse({'success': False, 'message': 'Duplicate transaction detected. Please wait a moment and try again.'})
            #Change computation
            change = amount_received - amount

            # 🧠 Check for recent duplicate transaction (same type, member, and amount)
            recent_time_limit = timezone.now() - timedelta(seconds=5)
            if Transactions.objects.filter(
                member_id=member,
                transaction_type=transaction_type,
                amount=amount,
                transaction_date__gte=recent_time_limit
            ).exists():
                return JsonResponse({'success': False, 'message': 'Duplicate transaction detected. Please wait a moment and try again.'})
            
            # --- SAVINGS DEPOSIT ---
            if transaction_type == 'Savings Deposit':
                savings = Savings.objects.select_for_update().get(member_id=member)
                savings.balance += amount
                savings.save()

                transaction_id = Transactions.objects.create(
                    member_id=member,
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    savings_id=savings
                )

                # 🔔 Member notification (different wording)
                notification = Notification.objects.create(
                    user_id=member.user_id,
                    title="Savings Deposit",
                    message=(
                        f"You deposited ₱{amount:,} into your savings account on "
                        f"{timezone.localtime().strftime('%b %d, %Y %I:%M %p')}. "
                        f"Your new balance is ₱{savings.balance:,}."
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
                
                toast_message = f"Savings deposit of ₱{amount} from Account #{member.account_number} completed successfully."

            # --- LOAN PAYMENT ---
            elif transaction_type == 'Loan Payment':
                loan = Loan.objects.select_for_update().filter(member_id=member, loan_status="Active").first()
                if not loan:
                    return JsonResponse({'success': False, 'message': 'No active loan for this member.'})
                
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
            
            # --- WITHDRAWAL ---
            elif transaction_type == 'Withdrawal':
                amount_received = None
                change = None
                savings = Savings.objects.select_for_update().get(member_id=member)
                current_loan = Loan.objects.filter(member_id=member, loan_status="Active").first()
                maintained_balance = current_loan.remaining_balance if current_loan else 0
                available_balance_to_withdraw = savings.balance - maintained_balance

                if available_balance_to_withdraw <= 0:
                    toast_message = f"Cannot proceed with withdrawal due to insufficient maintained balance."
                    return JsonResponse({"success": False, "message": toast_message})

                if available_balance_to_withdraw >= amount:
                    savings.balance -= amount
                    savings.save()
                    toast_message = f"Withdrawal of ₱{amount} from Account #{member.account_number} processed successfully."

                    # 🔔 Member notification (different wording)
                    notification = Notification.objects.create(
                        user_id=member.user_id,
                        title="Withdrawal",
                        message=(
                            f"You withdrew ₱{amount:,} from your savings account on "
                            f"{timezone.now().strftime('%b %d, %Y %I:%M %p')}. "
                            f"Remaining balance: ₱{savings.balance:,}."
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
                program = BusinessProgram.objects.filter(program_id=program_id).first()
                if not program:
                    return JsonResponse({"success": False, "message": "Invalid program selected."})

                # Update program total profit
                program.total_profit += amount
                program.save()

                # Record as revenue
                Revenue.objects.create(
                    source='Program Deposit',
                    amount=amount,
                    program_id=program
                )

                # Update fund balance
                Funds.objects.filter(fund_name='Revenue').update(balance=F('balance') + amount)

                transaction_id = Transactions.objects.create(
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    program_id=program
                )

                toast_message = f"Program deposit of ₱{amount:,.2f} added to {program.program_name} successfully."

            # --- Expense ---
            elif transaction_type == 'Operating Expenses':
                amount_received = None
                change = None

                expense_fund = Funds.objects.select_for_update().get(fund_name='Expenses')
                if amount > expense_fund.balance:
                    return JsonResponse({"success": False, "message": "Operating fund has insufficient balance!."})
                expense_fund.balance -= amount
                expense_fund.save()

                transaction_id = Transactions.objects.create(
                    cashier_id=cashier_id,
                    amount=amount,
                    amount_received=amount_received,
                    change=change,
                    transaction_type=transaction_type,
                    description=description
                )
                toast_message = f"Operating expense of ₱{amount:,.2f} recorded successfully."

            # --- Final Response Handling ---
            transaction = {
                "transaction_id": transaction_id.transaction_id,
                "transaction_type": transaction_id.transaction_type,
                "account_number": member.account_number if member else "N/A",
                "member_name": (
                    f"{member.person_id.first_name} {member.person_id.surname}"
                    if member and member.person_id else "N/A"
                ),
                "transaction_date": DateFormat(transaction_id.transaction_date).format("Y-m-d"),
                "amount_received": f"{transaction_id.amount_received or 0:.2f}",
                "amount": f"{transaction_id.amount or 0:.2f}",
                "change": f"{transaction_id.change or 0:.2f}",
            }

            return transaction_data(request, ajax=True, transaction=transaction, toast_message=toast_message)

    except IntegrityError:
        return JsonResponse({"success": False, "message": "Transaction failed. Please try again."})
    except Exception as e:
        return JsonResponse({"success": False, "message": f"An unexpected error occurred: {str(e)}"})


@transaction.atomic
def record_payment(member_id, loan, payment_amount):

    has_overdue = LoanRepaymentSchedule.objects.select_related('loan_id').filter(loan_id=loan, status="Overdue").exists()

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

        applicable_rebates = loan.loan_application_id.loan_type in [
            'Motorcycle Loan',
            'Appliances Loan',
            'Gadget Loan'
        ]

        if not has_overdue and applicable_rebates:
            # 1. ATOMICALLY UPDATE the balance (returns the number of rows updated)
            Savings.objects.filter(member_id=member_id).update(balance=F('balance') + loan.rebates)

            # 2. RETRIEVE the Savings object to use as the Foreign Key
            try:
                # Assuming 'member_id' uniquely identifies the Savings record
                savings_instance = Savings.objects.get(member_id=member_id) 
            except Savings.DoesNotExist:
                # Handle error if Savings record is somehow missing for the member
                return f"Error: Savings account not found for member {member_id.member_id}.", -1


            notification = Notification.objects.create(
                user_id=member_id.user_id,
                title="Loan Rebate Credited",
                message=f"A rebate of ₱{loan.rebates:,} has been credited to your savings account for timely loan payments."
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
            
            # 3. CREATE the Transaction, using the retrieved model instance
            Transactions.objects.create(
                member_id=member_id,
                amount=loan.rebates,
                transaction_type="Loan Rebate Credit",
                savings_id=savings_instance # Pass the actual Savings model instance
            )

        # update loan totals
        loan.total_paid = loan.total_paid + repayment.paid_amount if loan.total_paid else repayment.paid_amount
        loan.remaining_balance = max(0, loan.remaining_balance - repayment.paid_amount)
        loan.save()

        # ✅ Mark loan as Completed if fully paid
        if loan.remaining_balance == 0:
            loan.loan_status = "Completed"
            loan.save()
            notification = Notification.objects.create(
                user_id=member_id.user_id,
                title="Loan Fully Paid",
                message=f"Your due on {repayment.due_date.strftime('%b %d, %Y')} has been paid. Congratulations, your loan is fully paid!"
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
            # Next due
            next_due = LoanRepaymentSchedule.objects.filter(loan_id=loan, status__in=['Pending','Partially Paid']).order_by('due_date').first()
            note = f"Your due on {repayment.due_date.strftime('%b %d, %Y')} has been paid."
            if next_due:
                note += f" Next due: {next_due.due_date.strftime('%b %d, %Y')} amount ₱{next_due.amount_due:,}."
            notification = Notification.objects.create(
                user_id=member_id.user_id,
                title="Loan Due Paid",
                message=note
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
        notification = Notification.objects.create(
            user_id=member_id.user_id,
            title="Partial Loan Payment",
            message=f"Payment of ₱{payment_amount:,} recorded for due {repayment.due_date.strftime('%b %d, %Y')}. Remaining due: ₱{repayment.amount_due:,}."
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

    return f"Payment of ₱{payment_amount} from Account #{member_id.account_number} recorded successfully.", 0


def transaction_view(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = transaction_data(request, ajax=is_ajax)

    if is_ajax:
        return context  
    
    if user.groups.filter(name='Admin').exists():
        return render(request, 'transactions/admin_transaction.html', context)
        
    elif user.groups.filter(name='Member').exists():
        return render(request, 'transactions/member_transaction.html', context)
        
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'transactions/bookkeeper_transaction.html', context)
        
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'transactions/cashier_transaction.html', context)
        
    else:
        return HttpResponseForbidden("Unauthorized user group.")
    
def transaction_data(request, ajax=False, transaction=None, toast_message=None):
    user = request.user
    is_member = user.groups.filter(name='Member').exists()
    
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    
    start_date = None
    end_date = None
    
    current_query_params = ""
    if start_date_str:
        current_query_params += f"&start_date={start_date_str}"
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    if end_date_str:
        current_query_params += f"&end_date={end_date_str}"
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    transactions = (
        Transactions.objects
        .select_related("member_id")
        .order_by("-transaction_date")
    )
    
    table_partial_template = "transactions/partials/cashier_transaction_table_body.html"

    if is_member:
        transactions = transactions.filter(member_id__user_id=user)
        
        if start_date or end_date:
            filter_query = Q()
            if start_date:
                filter_query &= Q(transaction_date__gte=start_date)
            if end_date:
                filter_query &= Q(transaction_date__lte=end_date) 
            
            transactions = transactions.filter(filter_query)
        
        transactions = transactions.values(
            "transaction_id", "transaction_type", "transaction_date", "amount"
        )
        table_partial_template = "transactions/partials/member_transaction_table_body.html"
        
        members = []
        programs = []
        
    else:
        transactions = transactions.values(
            "transaction_id", "transaction_type", "member_id__account_number", 
            "transaction_date", "amount", "description"
        )

        members = (
            Member.objects
            .select_related("person_id")
            .values("account_number", "person_id__first_name", "person_id__middle_name", 
                    "person_id__name_extension", "person_id__surname")
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
        html = render_to_string(table_partial_template, {"page": page})
        
        pagination = render_to_string(
            "partials/pagination.html", 
            {
                "page": page,
                "current_query_params": current_query_params
            }
        )
        
        if is_member:
             return JsonResponse({"table_body_html": html, "pagination_html": pagination})
        
        return JsonResponse({"success": True, "message": toast_message, "table_body_html": html, "pagination_html": pagination, "transaction": transaction})
    
    context = {
        "members": members, 
        "programs": programs, 
        "page": page, 
        "start_date": start_date_str, 
        "end_date": end_date_str
    }
    return context


def balance(request):
    account_number = request.GET.get("accountNumber")
    transaction_type = request.GET.get("transactionType")

    if transaction_type == "Operating Expenses":
        fund = Funds.objects.filter(fund_name__iexact='Expenses').first()
        if not fund:
            return JsonResponse({
                "exists": True,
                "member_name": "Operating Account",
                "balance": 0
            })
        return JsonResponse({
            "exists": True,
            "member_name": "Operating Account",
            "balance": float(fund.balance)
        })

    member = Member.objects.select_related("person_id").filter(account_number=account_number).first()
    if not member:
        return JsonResponse({"exists": False, "balance": None})

    person = member.person_id
    member_name = ", ".join(
        part for part in [person.surname, person.first_name, person.middle_name, person.name_extension] if part
    )

    # 🟠 CASE 2A: Savings
    if transaction_type in ["Savings Deposit", "Withdrawal"]:
        savings = Savings.objects.filter(member_id=member).first()
        balance = savings.balance if savings else 0

    # 🔵 CASE 2B: Loan
    elif transaction_type == "Loan Payment":
        loan = Loan.objects.filter(member_id=member, loan_status="Active").first()
        balance = loan.remaining_balance if loan else 0

    # 🔴 Default
    else:
        balance = 0

    return JsonResponse({
        "exists": True,
        "member_name": member_name,
        "balance": float(balance)
    })

def passbook_print(request, account_number):
    # Fetch member
    member = Member.objects.select_related('person_id').get(account_number=account_number)

    # 1. Fetch Data (ordered ascending for calculation)
    # Note: Use 'pk' or 'id' as a secondary sort key for transactions on the same date.
    savings_transactions = Transactions.objects.filter(
        member_id=member,
        transaction_type__in=['Savings Deposit', 'Withdrawal', 'Dividend Credit']
    ).order_by('transaction_date', 'pk')

    loan_transactions = Transactions.objects.filter(
        member_id=member,
        transaction_type__in=['Loan Payment', 'Loan Release']
    ).select_related('loan_id__loan_application_id').order_by('transaction_date', 'pk')

    # 2. Initialize Starting Balances
    current_savings_balance = Decimal('0.00')
    current_loan_balance = Decimal('0.00')

    # 3. Calculate Running Savings Balance (CBU)
    for t in savings_transactions:
        try:
            # Ensure amount is a Decimal
            amount = t.amount if t.amount is not None else Decimal('0.00')
        except InvalidOperation:
            amount = Decimal('0.00') 

        if t.transaction_type in ['Savings Deposit', 'Dividend Credit']:
            current_savings_balance += amount
        elif t.transaction_type == 'Withdrawal':
            current_savings_balance -= amount
            
        t.savings_balance = current_savings_balance

    for t in loan_transactions:
        try:
            amount = t.amount if t.amount is not None else Decimal('0.00')
        except InvalidOperation:
            amount = Decimal('0.00')
        
        if t.transaction_type == 'Loan Release':
            current_loan_balance += t.loan_id.loan_application_id.total_payable
        elif t.transaction_type == 'Loan Payment':
            current_loan_balance -= amount
            
        t.loan_balance = current_loan_balance

    all_transactions = list(chain(savings_transactions, loan_transactions))
    
    all_transactions.sort(key=lambda t: t.transaction_date) 

    paginator = Paginator(all_transactions, 8)

    last_page_number = paginator.num_pages

    # Get the last page object
    last_page = paginator.page(last_page_number)

    context = {
        'member': member,
        'page': last_page,
    }

    return render(request, 'transactions/partials/passbook.html', context)