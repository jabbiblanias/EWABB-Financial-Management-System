from decimal import ROUND_HALF_UP, Decimal
from django.shortcuts import render, redirect
from members.models import Member,Savings
from loans.models import Loan, LoanPenalty, LoanRepaymentSchedule
from transactions.models import Transactions
from .models import Financialreports, Memberfinancialdata, Dividend, Funds
import json
from django.http import JsonResponse
from django.db.models import F, Case, When, Value, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from datetime import date
from django.utils import timezone
from django.db import transaction
from .utils import generate_unique_name
from django.http import HttpResponse
from django.template.loader import get_template, render_to_string
from django.core.paginator import Paginator 
from xhtml2pdf import pisa
from datetime import datetime
import csv
from datetime import date, timedelta
from django.db.models import Sum, Max
from django.db.models.functions import Round
from notifications.models import Notification


def member_loan_report(request):
    if request.user.groups.filter(name='Bookkeeper').exists():
        reports = Financialreports.objects.all().order_by("-last_updated")

        paginator = Paginator(reports, 10)

        page_num = request.GET.get('page')

        page = paginator.get_page(page_num)
        context = {'reports': reports, 'page': page}

        is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

        if is_ajax:
            html = render_to_string("financial_reporting/partials/reports_table_body.html", {"page": page})
            pagination = render_to_string("partials/pagination.html", {"page": page})
            return JsonResponse({"table_body_html": html, "pagination_html": pagination})
        
        return render(request, 'financial_reporting/bookkeeper_report.html', context)
    elif request.user.groups.filter(name='Admin').exists():
        reports = Financialreports.objects.filter(status="Submitted").all().order_by("-last_updated")

        paginator = Paginator(reports, 10)

        page_num = request.GET.get('page')

        page = paginator.get_page(page_num)
        context = {'reports': reports, 'page': page}

        is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

        if is_ajax:
            html = render_to_string("financial_reporting/partials/reports_table_body.html", {"page": page})
            pagination = render_to_string("partials/pagination.html", {"page": page})
            return JsonResponse({"table_body_html": html, "pagination_html": pagination})
        
        return render(request, 'financial_reporting/admin_report.html', context)
    

def monthly_report_details(request, report_id):
    report = Financialreports.objects.filter(report_id=report_id).values("title", "status").first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    context = {'financial_report': financial_report, 'title': report["title"], 'status': report["status"], 'report_id': report_id}
    if request.user.groups.filter(name='Bookkeeper').exists() or request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/members_report.html', context)

def dividend_report_details(request, report_id):
    report = Financialreports.objects.select_related('dividend_id').filter(report_id=report_id).first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    rate_percentage = (report.dividend_id.rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    context = {'financial_report': financial_report, 'title': report.title, 'status': report.status, 'report_id': report_id, "date": report.dividend_id.date_declared, "rate": rate_percentage}
    if request.user.groups.filter(name='Bookkeeper').exists() or request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/dividend_report.html', context)


def monthly_report(request):
    today = timezone.localdate()
    # Subquery: latest loan release date per member
    latest_loan_date = Loan.objects.filter(
        member_id=OuterRef('pk'), loan_status="Active"
    ).order_by('-released_date').values('released_date')[:1]

    # Subquery: latest overdue schedule id per member's active loan
    latest_overdue_schedule = LoanRepaymentSchedule.objects.filter(
        loan_id__member_id=OuterRef('pk'),
        status='Overdue'
    ).order_by('-schedule_id').values('schedule_id')[:1]

    # Subquery: latest penalty amount per schedule
    latest_penalty_amount = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk'), schedule_id__status='Overdue'
    ).order_by('-date_evaluated').values('penalty_amount')[:1]

    # Subquery: latest penalty date per schedule
    '''latest_penalty_date = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk')
    ).order_by('-date_evaluated').values('date_evaluated')[:1]'''

    # Subquery: active loan balance
    active_loan_balance = Loan.objects.filter(
        member_id=OuterRef('pk'),
        loan_status='Active'
    ).values('remaining_balance')[:1]

    # Main Query
    financial_report = Member.objects.select_related("person_id").annotate(
        loan_balance=Coalesce(
            Subquery(active_loan_balance),
            Value(0),
            output_field=DecimalField()
        ),
        released_date=Subquery(latest_loan_date),
        savings_balance=Coalesce(
            Subquery(
                Savings.objects.filter(member_id=OuterRef('pk')).values('balance')[:1]
            ),
            Value(0),
            output_field=DecimalField()
        ),
        schedule_id=Subquery(latest_overdue_schedule),
        penalty_amount=Subquery(latest_penalty_amount),
        #penalty_date=Subquery(latest_penalty_date),
    ).annotate(
        # Adjusted savings balance (savings + penalty if exists)
        savings_balance_with_penalty=Case(
            When(penalty_amount__isnull=False,
                then=F('savings_balance') + F('penalty_amount')),
            default=F('savings_balance'),
            output_field=DecimalField()
        ),
        # Savings after deduction = original savings 
        savings_after_deduction=F('savings_balance')
    )
    unique_title = generate_unique_name(Financialreports, 'title', f'monthly-report-{date.today().strftime("%Y-%m-%d")}')
    context = {'financial_report': financial_report, 'title': unique_title}
    if request.user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'financial_reporting/members_report.html', context)
    elif request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/members_report.html')
    
def dividend_report(request):
    today = timezone.localdate()

    # 1️⃣ Find the last dividend date range
    last_dividend = Dividend.objects.order_by('-period_end').first()

    if last_dividend:
        period_start = last_dividend.period_end + timedelta(days=1)
    else:
        # First ever dividend → start from start of the year
        period_start = date(date.today().year, 1, 1)

    # 2️⃣ Define the new period end (up to today)
    current_date = date.today()

    period_end = current_date

    total_savings = Savings.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')

    # 3️⃣ Get revenues & expenses within this new period
    total_income = Funds.objects.filter(fund_name='Revenue').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    total_expenses = Funds.objects.filter(fund_name='Expenses').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    print(total_income)
    print(total_expenses)

    net_surplus = total_income + total_expenses
    print(net_surplus)
    
    rate = (Decimal(net_surplus) / Decimal(total_savings)).quantize(Decimal('0.0001'))
    rate_percentage = (rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Subquery: latest loan release date per member
    latest_loan_date = Loan.objects.filter(
        member_id=OuterRef('pk'), loan_status="Active"
    ).order_by('-released_date').values('released_date')[:1]

    # Subquery: latest overdue schedule id per member's active loan
    latest_overdue_schedule = LoanRepaymentSchedule.objects.filter(
        loan_id__member_id=OuterRef('pk'),
        status='Overdue'
    ).order_by('-schedule_id').values('schedule_id')[:1]

    # Subquery: latest penalty amount per schedule
    latest_penalty_amount = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk'), schedule_id__status='Overdue'
    ).order_by('-date_evaluated').values('penalty_amount')[:1]

    # Subquery: latest penalty date per schedule
    '''latest_penalty_date = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk')
    ).order_by('-date_evaluated').values('date_evaluated')[:1]'''

    # Subquery: active loan balance
    active_loan_balance = Loan.objects.filter(
        member_id=OuterRef('pk'),
        loan_status='Active'
    ).values('remaining_balance')[:1]

    # Main Query
    financial_report = Member.objects.select_related("person_id").annotate(
        loan_balance=Coalesce(
            Subquery(active_loan_balance),
            Value(0),
            output_field=DecimalField()
        ),
        released_date=Subquery(latest_loan_date),
        savings_balance=Coalesce(
            Subquery(
                Savings.objects.filter(member_id=OuterRef('pk')).values('balance')[:1]
            ),
            Value(0),
            output_field=DecimalField()
        ),
        schedule_id=Subquery(latest_overdue_schedule),
        penalty_amount=Subquery(latest_penalty_amount),
        #penalty_date=Subquery(latest_penalty_date),
    ).annotate(
        # Adjusted savings balance (savings + penalty if exists)
        savings_balance_with_penalty=Case(
            When(penalty_amount__isnull=False,
                then=F('savings_balance') + F('penalty_amount')),
            default=F('savings_balance'),
            output_field=DecimalField()
        ),
        # Savings after deduction = original savings 
        savings_after_deduction=F('savings_balance'),
        total_savings_investment=F('savings_balance'),
        dividend_amount=Round(F('savings_balance') * rate, 2),
        updated_savings_investment=Round(F('savings_balance') + F('savings_balance') * rate, 2)
    ).order_by('member_id')
    unique_title = generate_unique_name(Financialreports, 'title', f'dividend-report-{date.today().strftime("%Y-%m-%d")}')
    context = {'financial_report': financial_report, 'title': unique_title, 'period_start': period_start, 'period_end': period_end, 'date': current_date,'rate': rate, 'rate_percentage': rate_percentage, 'net_surplus': net_surplus}
    if request.user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'financial_reporting/dividend_report.html')
    elif request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/dividend_report.html', context)
    
def compute_and_distribute_dividend():
    """Compute dividend for the next unprocessed period."""
    
    # 1️⃣ Find the last dividend date range
    last_dividend = Dividend.objects.order_by('-period_end').first()

    if last_dividend:
        period_start = last_dividend.period_end + timedelta(days=1)
    else:
        # First ever dividend → start from start of the year
        period_start = date(date.today().year, 1, 1)

    # 2️⃣ Define the new period end (up to today)
    period_end = date.today()

    total_savings = Savings.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    if total_savings <= 0:
        return {'success': False, 'message': 'No savings in the system — dividend not computed.'}

    # 3️⃣ Get revenues & expenses within this new period
    total_income = Funds.objects.filter(fund_name='Revenue').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
    total_expenses = Funds.objects.filter(fund_name='Expense').aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')

    net_surplus = total_income + total_expenses
    if net_surplus <= 0:
        return {'success': False, 'message': 'No surplus in this period — dividend not computed.'}
    
    rate = net_surplus / total_savings

    # 5️⃣ Create new dividend record
    dividend = Dividend.objects.create(
        title=f"Dividend ({period_start:%b %d, %Y} - {period_end:%b %d, %Y})",
        period_start=period_start,
        period_end=period_end,
        total_surplus=net_surplus,
        rate=rate,
    )

    # 6️⃣ Distribute to members
    members = Member.objects.all()
    total_distributed = Decimal('0.00')

    for member in members:
        share_capital = getattr(member, 'share_capital', Decimal('0.00'))
        if share_capital <= 0:
            continue

        dividend_amount = share_capital * dividend.rate
        total_distributed += dividend_amount

        # Credit to member savings
        if hasattr(member, 'savings_balance'):
            member.savings_balance += dividend_amount
            member.save()

    dividend.save()

    return {
        'success': True,
        'message': f"Dividend from {period_start:%b %d, %Y} to {period_end:%b %d, %Y} computed successfully.",
        'total_distributed': total_distributed,
        'period_start': period_start,
        'period_end': period_end,
    }

def submit_monthly_report(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    try:
        data = json.loads(request.body)
        title = data.get("title")
        action = data.get("action")
        report_id = data.get("report_id")
        members_data = data.get("members", {})

        if not members_data:
            return JsonResponse({"error": "No member data provided"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Use a database transaction to ensure atomicity
    with transaction.atomic():
        report_status = "Submitted" if action == "submit" else "Draft"
        if report_id:
            # You should use pk or another unique field to get a single object
            try:
                report = Financialreports.objects.get(pk=report_id)
                report.title = title
                report.status = report_status
                report.last_updated = timezone.now()
                report.save()
            except Financialreports.DoesNotExist:
                return JsonResponse({"error": f"Report with ID {report_id} not found"}, status=404)
        else:
            report = Financialreports.objects.create(title=title, status=report_status, report_type="monthly")

        # Create lists for objects to be updated and created
        to_update = []
        to_create = []
        
        # Find existing members to update using filter() and get all objects
        existing_members_queryset = Memberfinancialdata.objects.filter(
            account_number__in=members_data.keys(),
            report_id=report
        )
        
        # Create a dictionary for efficient lookup
        existing_members_dict = {
            member.account_number: member for member in existing_members_queryset
        }
        
        for account_no, values in members_data.items():
            # Check for the required 'remarks' key and ensure it's a string
            if not isinstance(values, dict):
                remarks = values
                if account_no in existing_members_dict:
                    member_instance = existing_members_dict[account_no]
                    member_instance.remarks = remarks
                    to_update.append(member_instance)
                else:
                    to_create.append(Memberfinancialdata(
                        account_number=account_no,
                        remarks=remarks,
                        report_id=report
                    ))
            else:
                if account_no in existing_members_dict:
                    member_instance = existing_members_dict[account_no]
                    member_instance.name = values.get("name", member_instance.name)
                    member_instance.outstanding_balance = values.get("outstanding_balance", member_instance.outstanding_balance)
                    member_instance.date_loaned = values.get("date_loaned", member_instance.date_loaned)
                    member_instance.savings = values.get("savings", member_instance.savings)
                    member_instance.penalty_charge = values.get("penalty_charge", member_instance.penalty_charge)
                    member_instance.savings_after_deduction = values.get("savings_after_deduction", member_instance.savings_after_deduction)
                    member_instance.remarks = values.get("remarks", member_instance.remarks)
                    to_update.append(member_instance)
                else:
                    to_create.append(Memberfinancialdata(
                        account_number=account_no,
                        name=values.get("name", ""),
                        outstanding_balance=values.get("outstanding_balance", 0),
                        date_loaned=values.get("date_loaned") or None,
                        savings=values.get("savings", 0),
                        penalty_charge=values.get("penalty_charge", 0),
                        savings_after_deduction=values.get("savings_after_deduction", 0),
                        remarks=values.get("remarks", ""),
                        report_id=report
                    ))

        # Use bulk operations for performance
        if to_create:
            Memberfinancialdata.objects.bulk_create(to_create)
        
        if to_update:
            # Collect the list of fields to update
            fields_to_update = ['remarks']
            Memberfinancialdata.objects.bulk_update(to_update, fields_to_update)
    
    return JsonResponse({"status": "success"}, status=200)

def submit_dividend_report(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)
    try:
        data = json.loads(request.body)
        title = data.get("title")
        period_start = data.get("period_start")
        period_end = data.get("period_end")
        rate = Decimal(data.get("rate"))
        net_surplus = Decimal(data.get("net_surplus"))
        members_data = data.get("members", {})

        if not members_data:
            return JsonResponse({"error": "No member data provided"}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Use a database transaction to ensure atomicity
    with transaction.atomic():
        current_year = timezone.localdate().year
        current_year_dividend = Dividend.objects.filter(period_end__year=current_year).exists()
        if current_year_dividend:
            return JsonResponse({"success": False, "message": "Dividend for the current year has already been processed."})
        
        dividend = Dividend.objects.create(
            period_start=period_start,
            period_end=period_end,
            total_surplus=net_surplus,
            rate=rate,
        )

        # 6️⃣ Distribute to members
        members = Member.objects.all()
        total_distributed = Decimal('0.00')

        for member in members:
            savings = Savings.objects.filter(member_id=member).first()
            if not savings or savings.balance <= 0:
                continue

            # Compute dividend
            dividend_amount = (savings.balance * Decimal(rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # 3️⃣ Credit dividend to member’s savings
            Savings.objects.filter(pk=savings.pk).update(balance=F('balance') + dividend_amount)
            total_distributed += dividend_amount

            # 4️⃣ Record a transaction entry for transparency
            Transactions.objects.create(
                member_id=member,
                transaction_type='Dividend Credit',
                amount=dividend_amount,
                transaction_date=date.today(),
                savings_id=savings
            )

            Notification.objects.create(
                member=member,
                title="Dividend Credit",
                message=f"You received ₱{dividend_amount:.2f} as your dividend for the Fiscal Year "
                        f"{current_year}.",
            )

        # Deduct total from Revenue fund once (after all members)
        revenue = Funds.objects.filter(fund_name='Revenue').first()
        if revenue:
            revenue.balance = Decimal('0.00')
            revenue.save(update_fields=['balance'])

        remains_from_net_surplus = net_surplus - total_distributed

        # If you want to clear Expenses fund (optional)
        expenses = Funds.objects.filter(fund_name='Expenses').first()
        if expenses:
            expenses.balance = remains_from_net_surplus  # or handle differently
            expenses.save(update_fields=['balance'])

        report = Financialreports.objects.create(title=title, status='Submitted', report_type="dividend", dividend_id=dividend)

        # Create lists for objects to be updated and created
        to_update = []
        to_create = []
        
        # Find existing members to update using filter() and get all objects
        existing_members_queryset = Memberfinancialdata.objects.filter(
            account_number__in=members_data.keys(),
            report_id=report
        )
        
        # Create a dictionary for efficient lookup
        existing_members_dict = {
            member.account_number: member for member in existing_members_queryset
        }
        
        for account_no, values in members_data.items():
            # Check for the required 'remarks' key and ensure it's a string
            if not isinstance(values, dict):
                remarks = values
                if account_no in existing_members_dict:
                    member_instance = existing_members_dict[account_no]
                    member_instance.remarks = remarks
                    to_update.append(member_instance)
                else:
                    to_create.append(Memberfinancialdata(
                        account_number=account_no,
                        remarks=remarks,
                        report_id=report
                    ))
            else:
                if account_no in existing_members_dict:
                    member_instance = existing_members_dict[account_no]
                    member_instance.name = values.get("name", member_instance.name)
                    member_instance.outstanding_balance = values.get("outstanding_balance", member_instance.outstanding_balance)
                    member_instance.date_loaned = values.get("date_loaned", member_instance.date_loaned)
                    member_instance.savings = values.get("savings", member_instance.savings)
                    member_instance.penalty_charge = values.get("penalty_charge", member_instance.penalty_charge)
                    member_instance.savings_after_deduction = values.get("savings_after_deduction", member_instance.savings_after_deduction)
                    member_instance.total_savings_investment = values.get("total_savings_investment", member_instance.total_savings_investment)
                    member_instance.dividend_amount = values.get("dividend_amount", member_instance.dividend_amount)
                    member_instance.updated_savings_investment = values.get("updated_savings_investment", member_instance.updated_savings_investment)
                    to_update.append(member_instance)
                else:
                    to_create.append(Memberfinancialdata(
                        account_number=account_no,
                        name=values.get("name", ""),
                        outstanding_balance=values.get("outstanding_balance", 0),
                        date_loaned=values.get("date_loaned") or None,
                        savings=values.get("savings", 0),
                        penalty_charge=values.get("penalty_charge", 0),
                        savings_after_deduction=values.get("savings_after_deduction", 0),
                        total_savings_investment=values.get("total_savings_investment", 0),
                        dividend_amount=values.get("dividend_amount", 0),
                        updated_savings_investment=values.get("updated_savings_investment", 0),
                        report_id=report
                    ))

        # Use bulk operations for performance
        if to_create:
            Memberfinancialdata.objects.bulk_create(to_create)
        
        if to_update:
            # Collect the list of fields to update
            fields_to_update = ['remarks']
            Memberfinancialdata.objects.bulk_update(to_update, fields_to_update)
    
    return JsonResponse({"success": True, "message": "Dividend report submitted successfully."})

def monthly_pdf_report_export(request, report_id):
    report = Financialreports.objects.filter(report_id=report_id).values("title", "status", "created_at").first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    template_path = 'financial_reporting/monthly_pdf_report.html'
    context = {'financial_report': financial_report, 'title': report["title"], 'status': report["status"], 'report_date': report["created_at"]}

    response = HttpResponse(content_type = 'application/pdf')
    response ['Content-Disposition'] = F'attachment; filename = "{report["title"]}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('we had some errors <pre>' + html + '</pre>')
    return response

def dividend_pdf_report_export(request, report_id):
    report = Financialreports.objects.filter(report_id=report_id).values("title", "status", "created_at").first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    template_path = 'financial_reporting/dividend_pdf_report.html'
    context = {'financial_report': financial_report, 'title': report["title"], 'status': report["status"], 'report_date': report["created_at"]}

    response = HttpResponse(content_type = 'application/pdf')
    response ['Content-Disposition'] = F'attachment; filename = "{report["title"]}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('we had some errors <pre>' + html + '</pre>')
    return response

def monthly_report_csv(request, report_id):
    report = Financialreports.objects.filter(
        report_id=report_id
    ).values("title", "status", "created_at").first()

    financial_report = Memberfinancialdata.objects.filter(report_id=report_id)

    response = HttpResponse(content_type="text/csv")
    response ['Content-Disposition'] = F'attachment; filename = "{report["title"]}.csv"'

    writer = csv.writer(response)

    # Write header row
    writer.writerow([
        "Account No",
        "Name",
        "Amount of Loan Balance",
        "Date Loaned",
        "Savings",
        "2% Penalty Charges",
        "Savings After Deduction",
        "Remarks",
        "Signature",
    ])

    # Write data rows
    for row in financial_report:
        writer.writerow([
            row.account_number,
            row.name,  # example of related name
            row.outstanding_balance,
            row.date_loaned.strftime("%b %d, %Y") if row.date_loaned else "",
            row.savings,
            row.penalty_charge,
            row.savings_after_deduction,
            row.remarks,
            "",
        ])

    return response


def dividend_report_csv(request, report_id):
    report = Financialreports.objects.filter(
        report_id=report_id
    ).values("title", "status", "created_at").first()

    financial_report = Memberfinancialdata.objects.filter(report_id=report_id)

    response = HttpResponse(content_type="text/csv")
    response ['Content-Disposition'] = F'attachment; filename = "{report["title"]}.csv"'

    writer = csv.writer(response)

    # Write header row
    writer.writerow([
        "Account No",
        "Name",
        "Amount of Loan Balance",
        "Date Loaned",
        "Savings",
        "2% Penalty Charges",
        "Savings After Deduction",
        "Total Savings / Investment",
        "Dividend Amount",
        "Updated Savings / Investment",
    ])

    # Write data rows
    for row in financial_report:
        writer.writerow([
            row.account_number,
            row.name,  # example of related name
            row.outstanding_balance,
            row.date_loaned.strftime("%b %d, %Y") if row.date_loaned else "",
            row.savings,
            row.penalty_charge,
            row.savings_after_deduction,
            row.remarks,
            "",
        ])

    return response

def check_last_dividend_date(request):
    current_year = timezone.localdate().year
    current_year_dividend = Dividend.objects.filter(period_end__year=current_year).exists()
    if current_year_dividend:
        return JsonResponse({"exists": True})
    return JsonResponse({"exists": False}, status=200)