from decimal import ROUND_HALF_UP, Decimal
from django.shortcuts import render
from members.models import Member,Savings
from loans.models import Loan, LoanPenalty, LoanRepaymentSchedule
from transactions.models import Transactions
from .models import Financialreports, Memberfinancialdata, Dividend, Funds
import json
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Case, When, Value, DecimalField, OuterRef, Subquery, Q, CharField, Sum
from django.db.models.functions import Coalesce, Concat, Round
from django.utils import timezone
from django.db import transaction
from .utils import generate_unique_name
from django.template.loader import get_template, render_to_string
from django.core.paginator import Paginator 
from xhtml2pdf import pisa
import csv
from datetime import date, timedelta
from notifications.models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.management import call_command
from urllib.parse import urlencode

def member_loan_report(request):
    # --- 1. Get request parameters ---
    search_term = request.GET.get('account', '').strip()
    sort_by = request.GET.get('sort_by', '').strip()
    order = request.GET.get('order', '').strip()
    page_num = request.GET.get('page')
    
    # --- 2. Fetch Data ---
    financial_report_qs = monthly_report_data(
        search_term=search_term,
        sort_by=sort_by,
        order=order
    )
    # dividend_report = dividend_report_data() # Assuming this function exists and is imported

    # --- 3. Pagination ---
    paginator = Paginator(financial_report_qs, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links, retaining filters/sorts
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'financial_report': page.object_list, # Only pass the current page's objects
        'page': page,                          # Pass the page object for pagination partial
        # 'dividend_report': dividend_report, # Uncomment when dividend_report_data is available
        'current_query_params': current_query_params,
    }

    # --- 4. AJAX / Standard Response ---
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    if is_ajax:
        # Render table body and pagination controls as HTML strings
        table_body_html = render_to_string(
            "financial_reporting/partials/member_data_table_body.html", 
            context, 
            request=request
        )
        pagination_html = render_to_string("partials/pagination.html", context, request=request)
        
        return JsonResponse({
            "table_body_html": table_body_html, 
            "pagination_html": pagination_html
        })

    # Standard (initial) page load
    if request.user.groups.filter(name__in=['Bookkeeper', 'Admin']).exists():
        return render(request, 'financial_reporting/financial_report.html', context)
    # Handle other user groups or lack of group appropriately
    # return redirect('some_other_page')
    

def monthly_pdf_report_export(request):
    financial_report = monthly_report_data()
    template_path = 'financial_reporting/monthly_pdf_report.html'
    context = {'financial_report': financial_report, "report_date": timezone.localdate()}

    response = HttpResponse(content_type = 'application/pdf')
    response ['Content-Disposition'] = F'attachment; filename = "Financial_Report_{timezone.localdate()}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('we had some errors <pre>' + html + '</pre>')
    return response

def dividend_pdf_report_export(request, report_id):
    report = Financialreports.objects.select_related('dividend_id').filter(report_id=report_id).first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    rate_percentage = (report.dividend_id.rate * 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    template_path = 'financial_reporting/dividend_pdf_report.html'
    context = {'financial_report': financial_report, 'title': report.title, 'status': report.status, 'report_id': report_id, "date": report.dividend_id.date_declared, "rate": rate_percentage}

    response = HttpResponse(content_type = 'application/pdf')
    response ['Content-Disposition'] = F'attachment; filename = "{report.title}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('we had some errors <pre>' + html + '</pre>')
    return response

def monthly_report_csv(request):
    financial_report = monthly_report_data()

    response = HttpResponse(content_type="text/csv")
    response ['Content-Disposition'] = F'attachment; filename = "Financial_Report_{timezone.localdate()}.csv"'

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
            row.person_id.first_name.upper() + " " + row.person_id.surname.upper(),  # example of related name
            row.loan_balance,
            row.released_date.strftime("%b %d, %Y") if row.released_date else "",
            row.savings_balance_with_penalty,
            row.penalty_amount,
            row.savings_after_deduction,
            "",
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
            row.person_id.first_name.upper() + " " + row.person_id.surname.upper(),  # example of related name
            row.loan_balance,
            row.released_date.strftime("%b %d, %Y") if row.released_date else "",
            row.savings_balance_with_penalty,
            row.penalty_amount,
            row.savings_after_deduction,
            row.total_savings_investment,
            row.dividend_amount,
            row.updated_savings_investment,
            "",
        ])

    return response

def check_last_dividend_date(request):
    current_year = timezone.localdate().year
    current_year_dividend = Dividend.objects.filter(period_end__year=current_year).exists()
    if current_year_dividend:
        return JsonResponse({"exists": True})
    return JsonResponse({"exists": False}, status=200)


def monthly_report_data(search_term=None, sort_by=None, order=None):
    today = timezone.localdate()
    
    # Subqueries (unchanged)
    latest_loan_date = Loan.objects.filter(
        member_id=OuterRef('pk'), loan_status="Active"
    ).order_by('-released_date').values('released_date')[:1]

    latest_overdue_schedule = LoanRepaymentSchedule.objects.filter(
        loan_id__member_id=OuterRef('pk'),
        status='Overdue'
    ).order_by('-schedule_id').values('schedule_id')[:1]

    latest_penalty_amount = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk'), schedule_id__status='Overdue'
    ).order_by('-date_evaluated').values('penalty_amount')[:1]

    active_loan_balance = Loan.objects.filter(
        member_id=OuterRef('pk'),
        loan_status='Active'
    ).values('remaining_balance')[:1]

    savings_balance_subquery = Savings.objects.filter(
        member_id=OuterRef('pk')
    ).values('balance')[:1]

    # Main Query Setup with Annotations for Sorting and Searching
    financial_report_qs = Member.objects.select_related("person_id").annotate(
        # Annotate field used for Name Sorting (Surname)
        surname_for_sort=F('person_id__surname'),
        
        # Annotate fields for full name searching (First Name + Surname)
        full_name_search=Concat(
            'person_id__first_name', Value(' '), 'person_id__surname',
            output_field=CharField()
        ),
        
        # Financial Annotations (unchanged)
        loan_balance=Coalesce(
            Subquery(active_loan_balance),
            Value(0),
            output_field=DecimalField()
        ),
        released_date=Subquery(latest_loan_date),
        savings_balance=Coalesce(
            Subquery(savings_balance_subquery),
            Value(0),
            output_field=DecimalField()
        ),
        schedule_id=Subquery(latest_overdue_schedule),
        penalty_amount=Subquery(latest_penalty_amount),
    ).annotate(
        # Adjusted savings balance calculation (unchanged)
        savings_balance_with_penalty=Case(
            When(penalty_amount__isnull=False,
                then=F('savings_balance') + F('penalty_amount')),
            default=F('savings_balance'),
            output_field=DecimalField()
        ),
        savings_after_deduction=F('savings_balance')
    )
    
    # --- APPLY FILTERING (Search by Account Number OR Name) ---
    if search_term:
        search_term = search_term.strip()
        final_filter = (
            Q(account_number__icontains=search_term) |             # Search Account Number
            Q(full_name_search__icontains=search_term) |          # Search Full Name (First Name Last Name)
            Q(person_id__surname__icontains=search_term) |        # Search Surname
            Q(person_id__first_name__icontains=search_term)       # Search First Name
        )
        financial_report_qs = financial_report_qs.filter(final_filter)
        
    # --- APPLY SORTING ---
    order_fields = []
    
    # Define allowed sortable fields
    ALLOWED_SORT_FIELDS = ['account_number', 'surname_for_sort', 'released_date'] 

    if sort_by in ALLOWED_SORT_FIELDS:
        db_sort_field = sort_by
        sort_field = f'-{db_sort_field}' if order == 'desc' else db_sort_field
        order_fields.append(sort_field)

    # Default sort order: By Account Number
    if not order_fields:
        order_fields.append('account_number')

    financial_report_qs = financial_report_qs.order_by(*order_fields)
    
    return financial_report_qs

from decimal import Decimal, ROUND_HALF_UP

def dividend_report_data():
    report = (
        Financialreports.objects
        .select_related('dividend_id')
        .order_by('-dividend_id__period_end')
        .first()
    )

    if not report:
        return None

    # If this report has NO dividend data, stop here safely
    if not report.dividend_id:
        return None

    financial_report = Memberfinancialdata.objects.filter(report_id=report)

    # Safe rate handling
    rate = report.dividend_id.rate
    if rate is None:
        rate_percentage = Decimal("0.00")
    else:
        rate_percentage = (rate * 100).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP
        )

    context = {
        "financial_report": financial_report,
        "title": report.title,
        "status": report.status,
        "report_id": report.report_id,
        "date": report.dividend_id.date_declared,
        "rate": rate_percentage,
    }

    return context

def run_annual_dividend_distribution(request):
    call_command('distribute_dividend')
    return JsonResponse({'status': 'success', 'job': 'annual dividend distribution executed'})