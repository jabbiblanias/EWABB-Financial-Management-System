from django.shortcuts import render, redirect
from accounts.models import Personalinfo
from members.models import Member
from loans.models import Loan, LoanPenalty
from .models import Financialreports, Memberfinancialdata
from transactions.models import Savings
import json
from django.http import JsonResponse

def financial_report_view(request):
    '''financial_report = (
        Member.objects.select_related('personalinfo', 'loan', 'savings', 'loanpenalty')
        .values(
            'accountnumber',
            'personalinfo__surname',
            'personalinfo__firstname',
            'personalinfo__nameextension',
            'personalinfo__middlename',
            'loan__outstandingbalance',
            'loan__releaseddate',
            'savings__amount'
        )
    )
    context = {'financial_report': financial_report}'''
    return render(request, 'financial_reporting/bookkeeper_report.html')


def submit_financial_report(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        title = data.get('title')
        reports = data.get('report', [])
        Financialreports.objects.create(
            title=title
        )

        for item in reports:
            Financialreports.objects.create(
                account_number=item['account_number'],
                surname=item['surname'],
                firstname=item['firstname'],
                outstanding_balance=item['outstanding_balance'],
                released_date=item['released_date'],
                savings_amount=item['savings_amount'],
                penalty_amount=item['penalty_amount']
            )

        return JsonResponse({'message': 'Report saved successfully'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)