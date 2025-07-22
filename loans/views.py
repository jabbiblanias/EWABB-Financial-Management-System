from django.shortcuts import render, redirect
from models import Loans, Member
from datetime import date
from django.contrib.auth.decorators import login_required

@login_required
def apply_loan(request):
    if request.method == 'POST':
        user=request.user
        member=Member.objects.get(user_id=user)

        loan_type = request.POST.get('loanType')
        loan_amount = request.POST.get('loanAmount')
        interest_rate = request.POST.get('interestRate')
        loan_term = request.POST.get('loanTerm')
        repayment_frequency = request.POST.get('loanType')
        total_payable = request.POST.get('loanType')
        monthly_amortization = request.POST.get('loanType')
        penalty_rate = request.POST.get('loanType')
        service_charge = request.POST.get('loanType')
        net_proceeds = request.POST.get('loanType') 

        Loans.objects.create(
            member=member,
            loan_type=loan_type,
            loan_amount=loan_amount,
            interest_rate=interest_rate,
            loan_term=loan_term,
            repayment_frequency=repayment_frequency,
            total_payable=total_payable,
            monthly_amortization=monthly_amortization,
            penalty_rate=penalty_rate,
            service_charge=service_charge,
            net_proceeds=net_proceeds
        )