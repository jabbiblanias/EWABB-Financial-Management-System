from django.shortcuts import render, redirect
from .models import LoanApplication, Member, Loan, LoanRepaymentSchedule
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration
from django.template.loader import render_to_string
from django.http import JsonResponse
import json
from django.contrib import messages


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
            context = loan_applications_data("Verified")
            return render(request, 'loans/admin_loan.html', context)
        elif user.groups.filter(name='Bookkeeper').exists():
            context = loan_applications_data("Pending")
            return render(request, 'loans/bookkeeper_loan.html', context)
        elif user.groups.filter(name='Cashier').exists():
            return render(request, 'loans/cashier_loan.html')
        

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


def bookkeeper_approved_loans(request):
    loans = (
        Loan.objects
        .select_related('member_id', 'loan_application_id')
        .order_by('-released_date')
        .values(
            'loan_id',
            'member_id__account_number',
            'loan_application_id__total_payable',
            'loan_application_id__net_proceeds',
            'outstanding_balance',
            'loan_status'
        )
    )
    context = {'loans' : loans}
    return render(request, 'loans/approved_loans.html', context)


def cashier_approved_loans(request):
    LoanApplication.objects.filter(status='Approved')
    
    
def loan_applications_data(status):
    loan_applications = (
        LoanApplication.objects
        .select_related('member_id')
        .filter(status=status)
        .values(
            'loan_application_id',
            'member_id__account_number',
            'loan_term_years',
            'loan_term_months',
            'loan_term_days',
            'loan_amount',
            'amortization'
        )
    )
    context = {'loanApplications': loan_applications}
    return context


def loan_application_details_view(request, loan_application_id):
    loan_application_details = LoanApplication.objects.select_related('member').get(loan_application_id=loan_application_id)
    context = {'loanApplicationDetails' : loan_application_details}
    return render(request, 'loan_application_details.html', context)


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
            context = loan_applications_data(status)
            html = render_to_string('loans/partials/loan_applications_table_body.html', context)
            return JsonResponse({'success': True, 'html': html})
        except LoanApplication.DoesNotExist:
            return JsonResponse({'success': False})