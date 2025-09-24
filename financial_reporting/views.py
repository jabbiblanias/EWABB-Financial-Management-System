from django.shortcuts import render, redirect
from members.models import Member,Savings
from loans.models import Loan, LoanPenalty, LoanRepaymentSchedule
from .models import Financialreports, Memberfinancialdata
import json
from django.http import JsonResponse
from django.db.models import F, Case, When, Value, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from datetime import date
from django.utils import timezone
from django.db import transaction
from .utils import generate_unique_name
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa


def member_loan_report(request):
    if request.user.groups.filter(name='Bookkeeper').exists():
        reports = Financialreports.objects.all()
        return render(request, 'financial_reporting/bookkeeper_report.html', {"reports": reports})
    elif request.user.groups.filter(name='Admin').exists():
        reports = Financialreports.objects.filter(status="Submitted").all()
        return render(request, 'financial_reporting/admin_report.html', {"reports": reports})
    

def report_details(request, report_id):
    report = Financialreports.objects.filter(report_id=report_id).values("title", "status").first()
    financial_report = Memberfinancialdata.objects.filter(report_id=report_id).all()
    context = {'financial_report': financial_report, 'title': report["title"], 'status': report["status"], 'report_id': report_id}
    if request.user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'financial_reporting/bookkeeper_members_report.html', context)
    elif request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/admin_report.html')


def generate_report(request):
    # Subquery: latest loan release date per member
    latest_loan_date = Loan.objects.filter(
        member_id=OuterRef('pk')
    ).order_by('-released_date').values('released_date')[:1]

    # Subquery: latest overdue schedule id per member's active loan
    latest_overdue_schedule = LoanRepaymentSchedule.objects.filter(
        loan_id__member_id=OuterRef('pk'),
        status='Overdue'
    ).order_by('-schedule_id').values('schedule_id')[:1]

    # Subquery: latest penalty amount per schedule
    latest_penalty_amount = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk')
    ).order_by('-date_evaluated').values('penalty_amount')[:1]

    # Subquery: latest penalty date per schedule
    latest_penalty_date = LoanPenalty.objects.filter(
        schedule_id__loan_id__member_id=OuterRef('pk')
    ).order_by('-date_evaluated').values('date_evaluated')[:1]

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
        penalty_date=Subquery(latest_penalty_date),
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
    unique_title = generate_unique_name(Financialreports, 'title', f'report-{date.today().strftime("%Y-%m-%d")}')
    context = {'financial_report': financial_report, 'title': unique_title}
    if request.user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'financial_reporting/bookkeeper_members_report.html', context)
    elif request.user.groups.filter(name='Admin').exists():
        return render(request, 'financial_reporting/admin_report.html')
    

def submit_financial_report(request):
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
            report = Financialreports.objects.create(title=title, status=report_status)

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
                        date_loaned=values.get("date_loaned"),
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

def pdf_report_export(request):
    financial_reporting = Financialreports.objects.all()
    template_path = 'pdf_convert/pdfReport.html'
    context = {'financial_reporting' : Financialreports}

    response = HttpResponse(content_type = 'application/pdf')
    response ['Content-Disposition'] = 'attachment; filename = "Financial_report.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)

    pisa_status = pisa.CreatePDF(
        html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('we had some errors <pre>' + html + '</pre>')
    return response