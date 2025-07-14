from django.shortcuts import render, redirect
from models import Loans, Member
from datetime import date
      
def apply_loan(request, MemberID):
    if request.method == 'POST':
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
        application_date = date.today()
        member=Member.objects.get(id=MemberID)

        Loans.objects.create(
            member=member,
            LoanType=loan_type,
            LoanAmount=loan_amount,
            InterestRate=interest_rate,
            LoanTerm=loan_term,
            RepaymentFrequency=repayment_frequency,
            TotalPayable=total_payable,
            MonthlyAmortization=monthly_amortization,
            PenaltyRate=penalty_rate,
            ServiceCharge=service_charge,
            NetProceeds=net_proceeds,
            ApplicationDate=application_date
        )