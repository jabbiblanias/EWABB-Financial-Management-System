from django.shortcuts import render, redirect
from .models import LoanApplication, Member, Loan, LoanRepaymentSchedule, LoanPenalty
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration, format_loan_term, compute_loan_breakdown
from django.template.loader import render_to_string
from django.http import JsonResponse
import json
from django.contrib import messages
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import OuterRef, Subquery
from notifications.models import Notification
from django.utils.dateformat import DateFormat
from django.core.paginator import Paginator 
from django.core.management import call_command
from django.db.models import Case, When, Value, IntegerField, Sum, Max, F
from decimal import ROUND_HALF_UP, Decimal
from members.models import Savings
from transactions.models import Transactions
from financial_reporting.models import Funds, Revenue, Expense


@login_required
def loan_application_view(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = loan_applications_data(request, ajax=is_ajax)

    if is_ajax:
        return context

    if user.groups.filter(name='Admin').exists():
        return render(request, 'loans/admin_loan.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'loans/bookkeeper_loan.html', context)
    elif user.groups.filter(name='Cashier').exists():
        context = cashier_approved_loans(request, ajax=is_ajax)
        return render(request, 'loans/cashier_loan.html', context)

@transaction.atomic
@login_required
def apply_loan(request):
    user = request.user
    if request.method == 'POST':
        try:
            loan_type = request.POST.get('loanType')
            loan_amount = Decimal(request.POST.get('loanAmount', 0))
            loan_term = request.POST.get('loanTerm')

            computed = compute_loan_breakdown(loan_amount, loan_term)

            years, months, days = parse_duration(loan_term)

            if user.groups.filter(name='Bookkeeper').exists():
                account_number = request.POST.get('accountNumber')
                member = Member.objects.get(account_number=account_number)
            else:
                member = Member.objects.get(user_id=user)
            savings = Savings.objects.get(member_id=member)
            print(savings.balance)

            if loan_amount <= savings.balance:
                loan_application = LoanApplication.objects.create(
                    member_id=member,
                    loan_type=loan_type,
                    loan_amount=loan_amount,
                    loan_term_years=years,
                    loan_term_months=months,
                    loan_term_days=days,
                    total_payable=computed["totalPayable"],
                    amortization=computed["amortization"],
                    cbu=computed["cbu"],
                    insurance=computed["insurance"],
                    service_charge=computed["serviceCharge"],
                    net_proceeds=computed["releaseAmount"]
                )
            else:
                return JsonResponse({"success": False, "message": "Insufficient savings balance."})

            is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
            if user.groups.filter(name='Bookkeeper').exists():
                context = loan_applications_data(request, ajax=is_ajax)
                html = render_to_string('loans/partials/loan_applications_table_body.html', context, request=request)
            else:
                context = member_loan_data(request, user, ajax=is_ajax)
                html = render_to_string('loans/partials/member_loan_table_body.html', context)

            return JsonResponse({
                "success": True,
                "message": f"Loan application ID {loan_application.loan_application_id} successfully created.",
                "loans": html
            })

        except Member.DoesNotExist:
            return JsonResponse({"success": False, "message": "Account number not found."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

@login_required
def member_loan_home(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = member_loan_data(request,user, ajax=is_ajax)

    if is_ajax:
        return context
    if request.user.groups.filter(name='Member').exists():
        return render(request, 'loans/member_loan.html', context)
    

def member_loan_data(request, user, ajax=False):
    member = Member.objects.get(user_id=user)

    loans = Loan.objects.filter(member_id=member).select_related("loan_application_id")
    loan_app_ids = loans.values_list('loan_application_id__loan_application_id', flat=True)

    loan_applications = LoanApplication.objects.filter(member_id=member).exclude(
        loan_application_id__in=loan_app_ids
    )

    combined = []

    for app in loan_applications:

        if app.status in ['Approved', 'Verified', 'Pending']:
            display_status = app.status
        else:
            display_status = 'Other'
        combined.append({
            "loan_application_id": app.loan_application_id,
            "loan_amount": app.loan_amount,
            "loan_term_years": app.loan_term_years,
            "loan_term_months": app.loan_term_months,
            "loan_term_days": app.loan_term_days,
            "loan_type": app.loan_type,
            "net_proceeds": app.net_proceeds,
            "amortization": app.amortization,
            "status": app.status,
            "display_status": display_status,
        })

    for loan in loans:
        app = loan.loan_application_id

        display_status = 'Active' if loan.loan_status == 'Active' else 'Completed'
        combined.append({
            "loan_application_id": app.loan_application_id,
            "loan_amount": app.loan_amount,
            "loan_term_years": app.loan_term_years,
            "loan_term_months": app.loan_term_months,
            "loan_term_days": app.loan_term_days,
            "loan_type": app.loan_type,
            "net_proceeds": loan.loan_application_id.net_proceeds,
            "amortization": app.amortization,
            "status": loan.loan_status,
            "display_status": display_status,
        })

    status_order = {'Approved': 1, 'Verified': 2, 'Pending': 3, 'Released': 4, 'Active': 5, 'Completed': 6, 'Other': 7}
    combined.sort(key=lambda x: status_order.get(x['display_status'], 99))

    paginator = Paginator(combined, 10)
    page = paginator.get_page(request.GET.get("page"))

    context = {"page": page}

    if ajax:
        html = render_to_string("loans/partials/member_loan_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})

    return context


@login_required
def active_loans(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = active_loans_data(request, ajax=is_ajax)

    if is_ajax:
        return context
    
    if user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'loans/bookkeeper_active_loans.html', context)
    elif user.groups.filter(name='Admin').exists(): 
        return render(request, 'loans/admin_active_loans.html', context)
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'loans/cashier_active_loans.html', context)


def active_loans_data(request, ajax=False):
    latest_due = LoanRepaymentSchedule.objects.filter(
        loan_id=OuterRef('pk'),
    ).exclude(
        status='Paid'
    ).order_by('due_date')

    loans = (
        Loan.objects
        #.filter(loan_status='Active')
        .select_related('member_id', 'loan_application_id')
        .annotate(
            amount_due=Subquery(latest_due.values('amount_due')[:1]),
            due_date=Subquery(latest_due.values('due_date')[:1]),
            status=Subquery(latest_due.values('status')[:1]),
        )
        .values(
            'loan_id',
            'loan_status',
            'member_id__account_number',
            'loan_application_id__loan_amount',
            'remaining_balance',
            'amount_due',
            'due_date',
            'status',
        )
        .order_by("due_date")
    )

    paginator = Paginator(loans, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'loans': loans, 'page': page}

    if ajax:
        html = render_to_string("loans/partials/active_loans_table_body.html", {"page": page}, request=request)
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True ,"table_body_html": html, "pagination_html": pagination})

    return context


def cashier_approved_loans(request, ajax=False):
    loans = (
        LoanApplication.objects.filter(status='Approved')
        .select_related('member_id')
        .values(
            'loan_application_id',
            'member_id__account_number',
            'loan_amount',
            'loan_term_years',
            'loan_term_months',
            'loan_term_days',
            'amortization',
            'status'
        )
        .order_by("-application_date")
    )

    paginator = Paginator(loans, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'loans': loans, 'page': page}

    if ajax:
        html = render_to_string("loans/partials/cashier_loan_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context

 
def loan_applications_data(request, ajax=False):
    user = request.user
    is_bookkeeper = user.groups.filter(name='Bookkeeper').exists()
    is_admin = user.groups.filter(name='Admin').exists()

    #Order priority based on role
    if is_bookkeeper:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    elif is_admin:
        status_order_case = Case(
            When(status='Verified', then=Value(1)),
            When(status='Pending', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    else:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

    loan_applications = (
        LoanApplication.objects
        .select_related('member_id')
        .annotate(status_order=status_order_case)
        .order_by('status_order', '-application_date')
        .values(
            'loan_application_id',
            'member_id',
            'member_id__account_number',
            'loan_term_years',
            'loan_term_months',
            'loan_term_days',
            'loan_amount',
            'amortization',
            'status'
        )
    )

    for loan in loan_applications:
        if loan['status'] == "Pending" or loan['status'] == "Verified":
            member_id = loan['member_id']
            risk_data = calculate_member_loan_risk(member_id)
            loan['risk_percentage'] = risk_data.get('risk_percentage')
            loan['risk_level'] = risk_data.get('risk_level')

    paginator = Paginator(loan_applications, 10)
    page_num = request.GET.get('page')
    page = paginator.get_page(page_num)

    context = {'page': page}

    if ajax:
        html = render_to_string("loans/partials/loan_applications_table_body.html", {"page": page}, request=request)
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context

@login_required
def loan_application_details_view(request, loan_application_id):
    loan_application_details = LoanApplication.objects.select_related('member_id', 'verifier_id', 'approver_id').get(loan_application_id=loan_application_id)
    verifier = (
        loan_application_details.verifier_id.get_full_name()
        if loan_application_details.verifier_id
        else None
    )

    approver = (
        loan_application_details.approver_id.get_full_name()
        if loan_application_details.approver_id
        else None
    )
    context = {'loan_application_details' : loan_application_details, "verifier": verifier, "approver": approver}
    return render(request, 'loans/loan_application_details.html', context)

@login_required
def loan_details_view(request, loan_id):
    loan = Loan.objects.select_related('member_id', 'released_by_id').get(loan_id=loan_id)

    user_name = loan.released_by_id.get_full_name()
    account_number = loan.member_id.account_number
    schedules = (
        LoanRepaymentSchedule.objects
        .select_related('loan_id__loan_application_id')
        .filter(loan_id=loan)
        .values(
            "schedule_id",
            "due_date",
            "loan_id__loan_application_id__amortization",
            "amount_due",
            "status",
            "paid_amount",
            "paid_date",
            "last_updated"
        )
        .order_by("due_date")
    )
    context = {
        'loan' : loan, 
        'user_name': user_name,
        'account_number': account_number,
        'schedules': schedules
    }
    return render(request, 'loans/loan_details.html', context)


@login_required
def member_loan_details_view(request, loan_application_id):
    loan_application_details = (
        LoanApplication.objects
        .select_related('member_id', 'verifier_id', 'approver_id')
        .get(loan_application_id=loan_application_id)
    )

    verifier = (
        loan_application_details.verifier_id.get_full_name()
        if loan_application_details.verifier_id else None
    )
    approver = (
        loan_application_details.approver_id.get_full_name()
        if loan_application_details.approver_id else None
    )

    # ✅ Check if the loan application already has a loan
    loan = (
        Loan.objects
        .select_related('member_id', 'released_by_id')
        .filter(loan_application_id=loan_application_id)
        .first()
    )

    # If loan exists, get schedules — otherwise skip
    schedules = []
    user_name = None
    account_number = None

    if loan:
        user_name = loan.released_by_id.get_full_name()
        account_number = loan.member_id.account_number

        schedules = (
            LoanRepaymentSchedule.objects
            .select_related('loan_id__loan_application_id')
            .filter(loan_id=loan)
            .values(
                "schedule_id",
                "due_date",
                "loan_id__loan_application_id__amortization",
                "amount_due",
                "status",
                "paid_amount",
                "paid_date",
                "last_updated"
            )
            .order_by("due_date")
        )

    context = {
        'loan_application_details': loan_application_details,
        'verifier': verifier,
        'approver': approver,
        'loan': loan,
        'user_name': user_name,
        'account_number': account_number,
        'schedules': schedules
    }

    return render(request, 'loans/member_loan_details.html', context)


@transaction.atomic
@login_required
def approving_loan(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        loan_application_id = data.get('loan_application_id')
        action = data.get('action')
        user = request.user
        bookkeeper = user.groups.filter(name='Bookkeeper').exists()
        admin = user.groups.filter(name='Admin').exists()
        status = ""

        try:
            loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)
            member = loan_application.member_id
            if bookkeeper:
                if action == 'approve':
                    loan_application.status = 'Verified'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Verified",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) has been verified and is now under review for approval. "
                                    f"Please wait for further updates."
                    )
                elif action == 'reject':
                    loan_application.status = 'Rejected'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Rejected",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) was declined. "
                                f"For more information, please message us or contact the office."
                    )

                loan_application.verifier_id = user
                loan_application.verified_date = date.today()
                status = "Pending"
            elif admin:
                if action == 'approve':
                    loan_application.status = 'Approved'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Approved",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) has been approved. "
                                    f"Amount: ₱{loan_application.loan_amount:.2f}, Term: {format_loan_term(loan_application)}. "
                                    f"Please proceed to the cashier to finalize the release."
                    )

                elif action == 'reject':
                    loan_application.status = 'Rejected'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Rejected",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) was declined. "
                                f"For more information, please message us or contact the office."
                    )
                loan_application.approver_id = user
                loan_application.approved_date = date.today()
                status = "Verified"
            loan_application.save()

            # get shared data
            context = loan_applications_data(request, ajax=True)
            return context
        except LoanApplication.DoesNotExist:
            return JsonResponse({'success': False})
        except Member.DoesNotExist:
            return JsonResponse({'success': False})

@login_required
@transaction.atomic
def releasing(request):
    data = json.loads(request.body)
    loan_application_id = data.get('loan_application_id')
    user = request.user

    try:
        # Lock the loan application to prevent race conditions
        loan_application = (
            LoanApplication.objects
            .select_for_update()
            .get(loan_application_id=loan_application_id)
        )

        # 🔒 Prevent double releasing
        if loan_application.status != 'Approved':
            return JsonResponse({
                'success': False,
                'message': f"Loan has already been {loan_application.status.lower()}."
            })

        member = loan_application.member_id

        # Double-check that the loan doesn’t already exist (extra safety)
        if Loan.objects.filter(loan_application_id=loan_application).exists():
            return JsonResponse({
                'success': False,
                'message': 'This loan has already been released.'
            })

        # ✅ Proceed with loan creation
        loan = Loan.objects.create(
            member_id=member,
            loan_application_id=loan_application,
            remaining_balance=loan_application.total_payable,
            released_by_id=user
        )

        loan_days = loan_application.loan_term_days
        loan_years = loan_application.loan_term_years
        loan_months = loan_application.loan_term_months
        amortization = Decimal(loan_application.amortization)
        released_date = date.today()

        if loan_days == 100 and loan_months == 0 and loan_years == 0:
            LoanRepaymentSchedule.objects.create(
                loan_id=loan,
                due_date=released_date + relativedelta(days=loan_days),
                amount_due=loan_application.total_payable,
            )
        else:
            total_months = (loan_years * 12) + loan_months
            payment_date = released_date

            base_amortization = (loan_application.total_payable / total_months).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_rounded = base_amortization * total_months
            difference = (loan_application.total_payable - total_rounded).quantize(Decimal('0.01'))
            last_amortization = (base_amortization + difference).quantize(Decimal('0.01'))

            for i in range(total_months):
                payment_date += relativedelta(months=1)
                amount_due = last_amortization if i == total_months - 1 else amortization
                LoanRepaymentSchedule.objects.create(
                    loan_id=loan,
                    due_date=payment_date,
                    amount_due=amount_due,
                )
            
        applicable_rebates = loan.loan_application_id.loan_type in [
            'Motorcycle Loan',
            'Appliances Loan',
            'Gadget Loan'
        ]

        if applicable_rebates:
            loan.rebates = loan.loan_application_id.cbu / total_months
            loan.save()

        # Update loan application status
        loan_application.status = "Released"
        loan_application.save()

        # Update financials
        Member.objects.filter(member_id=member.member_id).update(
            insurance=F('insurance') + loan_application.insurance
        )

        Savings.objects.filter(member_id=member.member_id).update(
            balance=F('balance') + loan_application.cbu
        )

        Revenue.objects.create(
            source='Service Charge',
            member_id=member,
            amount=loan_application.service_charge / Decimal('2'),
            loan_id=loan
        )

        Expense.objects.create(
            source='Service Charge',
            member_id=member,
            amount=loan_application.service_charge / Decimal('2'),
            loan_id=loan
        )

        Funds.objects.filter(fund_name='Expenses').update(
            balance=F('balance') + (Decimal(loan_application.service_charge) / Decimal('2'))
        )

        Funds.objects.filter(fund_name='Revenue').update(
            balance=F('balance') + (Decimal(loan_application.service_charge) / Decimal('2'))
        )

        Transactions.objects.create(
            member_id=member,
            cashier_id=user,
            amount=loan_application.net_proceeds,
            transaction_type='Loan Release',
            loan_id=loan
        )

        schedules = LoanRepaymentSchedule.objects.filter(loan_id=loan).values("due_date").order_by("due_date").first()

        Notification.objects.create(
            user_id=member.user_id,
            title="Loan Released",
            message=(
                f"Your approved loan (ID: {loan.loan_id}) has been successfully released. "
                f"Amount Released: ₱{loan_application.net_proceeds:,.2f}. "
                f"Start date of repayment: {DateFormat(schedules['due_date']).format('M d, Y')}."
            )
        )

        # Return updated UI content
        context = cashier_approved_loans(request, ajax=True)
        return context

    except LoanApplication.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Loan application not found.'})
    except Member.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Member not found.'})



def run_repayment_status_update(request):
    call_command('update_repayment_status')
    return JsonResponse({'status': 'success', 'job': 'daily repayment status update executed'})

def compute_loan_details(request):
    try:
        loan_amount = Decimal(request.GET.get('loanAmount', 0))
        term = request.GET.get('loanTerm', '')

        data = compute_loan_breakdown(loan_amount, term)
        return JsonResponse({"success": True, "data": data})

    except ValueError as ve:
        return JsonResponse({"success": False, "message": str(ve)})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


def calculate_member_loan_risk(member_id):
    try:
        loans = Loan.objects.filter(member_id=member_id).order_by('released_date')
        if not loans.exists():
            return {
                "member_id": member_id,
                "risk_percentage": 0,
                "risk_level": "No Loan History",
            }

        schedules = LoanRepaymentSchedule.objects.filter(loan_id__in=loans)
        penalties = LoanPenalty.objects.filter(schedule_id__loan_id__in=loans)

        total_schedules = schedules.count()
        total_penalties = penalties.count()
        total_penalty_amount = penalties.aggregate(total=Sum('penalty_amount'))['total'] or Decimal('0.00')

        total_payable = LoanApplication.objects.filter(
            loan_application_id__in=loans.values_list('loan_application_id', flat=True)
        ).aggregate(total=Sum('total_payable'))['total'] or Decimal('0.00')

        # --- Risk Factors ---
        penalty_frequency_ratio = (total_penalties / total_schedules) if total_schedules > 0 else 0
        penalty_amount_ratio = (float(total_penalty_amount) / float(total_payable)) if total_payable > 0 else 0

        # Loan Growth Ratio (based on highest previous loan)
        current_loan = loans.last()
        current_amount = float(current_loan.loan_application_id.loan_amount)
        previous_max = float(
            loans.exclude(pk=current_loan.pk)
                 .aggregate(max_amt=Max('loan_application_id__loan_amount'))['max_amt'] or 0
        )
        loan_growth_ratio = max((current_amount / previous_max - 1), 0) if previous_max > 0 else 0

        # --- Weighted Risk Formula ---
        risk_score = (
            (penalty_frequency_ratio * 0.55) +
            (penalty_amount_ratio * 0.30) +
            (loan_growth_ratio * 0.15)
        )

        risk_percentage = min(round(risk_score * 100, 2), 100)

        # --- Risk Interpretation ---
        if risk_percentage < 25:
            risk_level = "Low"
        elif risk_percentage < 50:
            risk_level = "Moderate"
        elif risk_percentage < 75:
            risk_level = "High"
        else:
            risk_level = "Critical"

        return {
            "member_id": member_id,
            "risk_percentage": risk_percentage,
            "risk_level": risk_level,
            "total_loans": loans.count(),
            "total_penalties": total_penalties,
            "total_penalty_amount": float(total_penalty_amount),
            "loan_growth_ratio": round(loan_growth_ratio, 2),
        }

    except Exception as e:
        return {"error": str(e)}

def member_savings(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        savings = Savings.objects.get(member_id=member)
        member_savings = savings.balance
        return JsonResponse({"success": True, "member_savings": member_savings})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})
    except Savings.DoesNotExist:
        return JsonResponse({"success": False, "message": "Savings record not found."})
    
def check_active_loan(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        
        active_loan_exists = Loan.objects.filter(member_id=member, loan_status='Active').exists()
        print(active_loan_exists)
        return JsonResponse({"success": True, "active_loan_exists": active_loan_exists})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})

def check_active_loan_and_remaining_balance(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        
        active_loan = Loan.objects.filter(member_id=member, loan_status='Active').first()
        if active_loan:
            remaining_balance = active_loan.remaining_balance
            return JsonResponse({"success": True, "active_loan_exists": True, "remaining_balance": remaining_balance})
        else:
            return JsonResponse({"success": True, "active_loan_exists": False, "remaining_balance": None})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})