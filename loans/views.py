from django.shortcuts import render, redirect
from .models import LoanApplication, Member, Loan, LoanRepaymentSchedule
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration
from django.template.loader import render_to_string
from django.http import JsonResponse
import json
from django.contrib import messages
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import OuterRef, Subquery


@login_required
def loan_application_view(request):
    user = request.user
    if request.method == 'POST':
        loan_type = request.POST.get('loanType')
        loan_amount = request.POST.get('loanAmount')
        loan_term = request.POST.get('loanTerm')
        total_payable = request.POST.get('totalPayable')
        amortization = request.POST.get('amortization')
        cbu = request.POST.get('cbu')
        insurance = request.POST.get('insurance')
        service_charge = request.POST.get('serviceCharge')
        net_proceeds = request.POST.get('releaseAmount') 

        years, months, days = parse_duration(loan_term)
        if user.groups.filter(name='Bookkeeper').exists():
            account_number=request.POST.get('accountNumber')
            member=Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member=Member.objects.get(user_id=user)

        LoanApplication.objects.create(
            member_id=member,
            loan_type=loan_type,
            loan_amount=loan_amount,
            loan_term_years=years,
            loan_term_months=months,
            loan_term_days=days,
            total_payable=total_payable,
            amortization=amortization,
            cbu=cbu,
            insurance=insurance,
            service_charge=service_charge,
            net_proceeds=net_proceeds
        )
        if user.groups.filter(name='Bookkeeper').exists():
            return redirect('loan_applications')
        elif user.groups.filter(name='Member').exists():
            return redirect('loans')
    else:
        if user.groups.filter(name='Admin').exists():
            context = loan_applications_data()
            return render(request, 'loans/admin_loan.html', context)
        elif user.groups.filter(name='Bookkeeper').exists():
            context = loan_applications_data()
            return render(request, 'loans/bookkeeper_loan.html', context)
        elif user.groups.filter(name='Cashier').exists():
            context = cashier_approved_loans()
            return render(request, 'loans/cashier_loan.html', context)
        

@login_required
def member_loan_home(request):
    user = request.user
    if request.user.groups.filter(name='Member').exists():
        context = member_loan_data(user)
        return render(request, 'loans/member_loan.html', context)
    else:
        return redirect('loan_applications')
    

def member_loan_data(user):
    member = Member.objects.get(user_id=user)
    loans = (
        LoanApplication.objects
        .filter(member_id=member)
        .values(
            'loan_type',
            'loan_amount',
            'loan_term_years',
            'loan_term_months',
            'loan_term_days',
            'net_proceeds',
            'amortization',
            'status'
        )
    )
    context = {'loans': loans}
    return context


@login_required
def active_loans(request):
    user = request.user
    status_filter = ''
    if user.groups.filter(name='Bookkeeper').exists():
        status_filter = 'Verified' or 'Approved'
        context = active_loans_data()
        return render(request, 'loans/bookkeeper_active_loans.html', context)
    elif user.groups.filter(name='Admin').exists():
        status_filter = 'Approved' 
        context = active_loans_data()  
        return render(request, 'loans/admin_active_loans.html', context)
    elif user.groups.filter(name='Cashier').exists():
        status_filter = 'Approved' 
        context = active_loans_data()  
        return render(request, 'loans/cashier_active_loans.html', context)


def active_loans_data():
    # Subquery: get the earliest unpaid repayment for each loan
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

    return {'loans': loans}


def cashier_approved_loans():
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
    )
    context = {'loans' : loans}
    return context

 
def loan_applications_data():
    loan_applications = (
        LoanApplication.objects
        .select_related('member_id')
        .values(
            'loan_application_id',
            'member_id__account_number',
            'loan_term_years',
            'loan_term_months',
            'loan_term_days',
            'loan_amount',
            'amortization',
            'status'
        )
    )
    context = {'loanApplications': loan_applications}
    return context

@login_required
def loan_application_details_view(request, loan_application_id):
    loan_application_details = LoanApplication.objects.select_related('member_id').get(loan_application_id=loan_application_id)
    context = {'loan_application_details' : loan_application_details}
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
            if bookkeeper:
                if action == 'approve':
                    loan_application.status = 'Verified'
                elif action == 'reject':
                    loan_application.status = 'Rejected'
                loan_application.verifier_id = user
                loan_application.verified_date = date.today()
                status = "Pending"
            elif admin:
                if action == 'approve':
                    loan_application.status = 'Approved'
                elif action == 'reject':
                    loan_application.status = 'Rejected'
                loan_application.approver_id = user
                loan_application.approved_date = date.today()
                status = "Verified"
            loan_application.save()
            context = loan_applications_data()
            html = render_to_string('loans/partials/loan_applications_table_body.html', context)
            return JsonResponse({'success': True, 'html': html})
        except LoanApplication.DoesNotExist:
            return JsonResponse({'success': False})


@login_required
@transaction.atomic
def releasing(request):
    data = json.loads(request.body)
    loan_application_id = data.get('loan_application_id')
    account_number = data.get('account_number')
    try:
        loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id, status='Approved')
        member = Member.objects.get(account_number=account_number)
        loan = Loan.objects.create(
            member_id=member,
            loan_application_id=loan_application,
            remaining_balance=loan_application.total_payable,
            released_by_id=request.user
        )

        loan_days = loan_application.loan_term_days
        loan_years = loan_application.loan_term_years
        loan_months = loan_application.loan_term_months
        amortization = float(loan_application.amortization)
        released_date = date.today()

        if loan_days == 100 and loan_months == 0 and loan_years == 0:
            LoanRepaymentSchedule.objects.create(
                loan_id=loan,
                due_date=released_date + relativedelta(days=loan_days),
                amount_due=loan_application.total_payable,
            )
        else:
            total_months = loan_years * 12 + loan_months
            total_days = total_months * 30 + loan_days
            remaining_days = total_days
            payment_date = released_date
            while remaining_days > 0:
                payment_date += relativedelta(days=30)
                LoanRepaymentSchedule.objects.create(
                    loan_id=loan,
                    due_date=payment_date,
                    amount_due=amortization,
                )
                remaining_days -= 30
        loan_application.status = "Released"
        loan_application.save()
        context = cashier_approved_loans()
        html = render_to_string('loans/partials/cashier_loan_table_body.html', context)
        return JsonResponse({'success': True, 'html': html})
    except (LoanApplication.DoesNotExist, Member.DoesNotExist):
        return JsonResponse({'success': False})
    

def update_loan():
    print()