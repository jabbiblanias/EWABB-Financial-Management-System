from django.shortcuts import render, redirect
from .models import LoanApplication, Member
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration

@login_required
def loan_application_view(request):
    if request.method =='POST':
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            loan_application_id = request.POST.get('loanid')
            loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)
            loan_application.verifier_id = user
            loan_application.verified_date = date.today()
            loan_application.status = 'Verified'
        elif user.groups.filter(name='Admin').exists():
            loan_application_id = request.POST.get('loanid')
            loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)
            loan_application.approver_id = user
            loan_application.approved_date = date.today()
            loan_application.status = 'Approved'
    loan_applications = LoanApplication.objects.select_related('member').all()
    return render(request, 'loan_applications.html', {'loan_applications': loan_applications})


@login_required
def apply_loan(request):
    if request.method == 'POST':
        user=request.user

        loan_type = request.POST.get('loanType')
        loan_amount = request.POST.get('loanAmount')
        interest_rate = request.POST.get('interestRate')
        loan_term = request.POST.get('loanTerm')
        total_payable = request.POST.get('totalPayable')
        monthly_amortization = request.POST.get('monthlyAmortization')
        cbu = request.POST.get('cbu')
        insurance = request.POST.get('insurance')
        service_charge = request.POST.get('serviceCharge')
        net_proceeds = request.POST.get('netProceeds') 

        years, months, days = parse_duration(loan_term)
        if user.groups.filter(name='Bookkeeper').exists():
            account_number=request.POST.get('accountNumber')
            member=Member.objects.get(account_number=account_number)
        else:
            member=Member.objects.get(user_id=user)

        LoanApplication.objects.create(
            member_id=member,
            loan_type=loan_type,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            loan_term_years=years,
            loan_term_months=months,
            loan_term_days=days,
            total_payable=total_payable,
            monthly_amortization=monthly_amortization,
            cbu=cbu,
            insurance=insurance,
            service_charge=service_charge,
            net_proceeds=net_proceeds
        )


@login_required
def approving_loan(request):
    if request.method == 'POST':
        user = request.user
        loan_application_id = request.POST.get('applicationid')

        try:
            loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)

            if user.groups.filter('Bookkeeper').exists():
                loan_application.verifier_id = user
                loan_application.verified_date = date.today()
                loan_application.save()
            elif user.groups.filter('Admin').exists():
                loan_application.approver_id = user
                loan_application.approved_date = date.today()
                loan_application.save()
        except LoanApplication.DoesNotExist:
            print("Loan application record not found.")