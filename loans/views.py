from django.shortcuts import render, redirect
from .models import LoanApplication, Member
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration


@login_required
def loan_application_view(request):
    loan_applications = LoanApplication.objects.select_related('member').filter(status='Pending').values('loanapplicationid')
    context = {'loan_applications': loan_applications}
    return render(request, 'loan_applications.html', context)


def loan_application_details(request, loan_application_id):
    loan_application_details = LoanApplication.objects.get(loan_application_id=loan_application_id)
    context = {'loanApplicationDetails' : loan_application_details}
    return render(request, 'loan_application_details.html', context)


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
def approving_loan(request, loan_application_id, action):
    if request.method == 'POST':
        user = request.user
        loan_application_id = request.POST.get('applicationid')

        try:
            loan_application = LoanApplication.objects.get(loan_application_id=loan_application_id)
            if action == 'approve':
                if user.groups.filter('Bookkeeper').exists():
                    loan_application.status = 'Verified'
                    loan_application.verifier_id = user
                    loan_application.verified_date = date.today()
                elif user.groups.filter('Admin').exists():
                    loan_application.status = 'Approved'
                    loan_application.approver_id = user
                    loan_application.approved_date = date.today()
            elif action == 'reject':
                loan_application.status = 'Rejected'
            loan_application.save()
            
        except LoanApplication.DoesNotExist:
            print("Loan application record not found.")