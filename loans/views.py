from django.shortcuts import render, redirect
from .models import LoanApplication, Member, Loan, LoanRepaymentSchedule, LoanPenalty
from django.contrib.auth.decorators import login_required
from datetime import date
from .utils import parse_duration, format_loan_term, compute_loan_breakdown
from django.template.loader import render_to_string
from django.http import JsonResponse
import json
from django.contrib import messages
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.db.models import OuterRef, Subquery
from notifications.models import Notification
from django.utils.dateformat import DateFormat
from django.core.paginator import Paginator 
from django.core.management import call_command
from django.db.models import Case, When, Value, IntegerField, Sum, Max, F, Q
from decimal import ROUND_HALF_UP, Decimal
from members.models import Savings
from transactions.models import Transactions
from financial_reporting.models import Funds, Revenue, Expense
from django.core.paginator import Paginator
from urllib.parse import urlencode


@login_required
def loan_application_view(request):
    user = request.user
    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    # --- 1. Determine User Group and Call Appropriate Data Function ---
    if user.groups.filter(name='Admin').exists() or user.groups.filter(name='Bookkeeper').exists():
        template_name = 'loans/admin_loan.html' if user.groups.filter(name='Admin').exists() else 'loans/bookkeeper_loan.html'
        
        # Call the generic data function for Admin/Bookkeeper
        context = loan_applications_data(request, ajax=is_ajax)
        
    elif user.groups.filter(name='Cashier').exists():
        template_name = 'loans/cashier_loan.html'
        
        # Call the specific Cashier data function
        context = cashier_approved_loans(request, ajax=is_ajax)
        
    else:
        # Handle users with no relevant group (e.g., redirect or error)
        return render(request, 'error_page.html', {'message': 'Unauthorized access'})

    # --- 2. Handle AJAX or Full Render ---
    if is_ajax:
        # This will return the JsonResponse object from whichever data function was called above.
        return context

    # If not AJAX, render the appropriate full page template.
    return render(request, template_name, context)

@transaction.atomic
@login_required
def apply_loan(request):
    user = request.user
    if request.method == 'POST':
        try:
            loan_type = request.POST.get('loanType')
            loan_amount = Decimal(request.POST.get('loanAmount', 0))
            loan_term = request.POST.get('loanTerm')

            computed = compute_loan_breakdown(loan_amount, loan_term)

            years, months, days = parse_duration(loan_term)

            if user.groups.filter(name='Bookkeeper').exists():
                account_number = request.POST.get('accountNumber')
                member = Member.objects.get(account_number=account_number)
            else:
                member = Member.objects.get(user_id=user)
            savings = Savings.objects.get(member_id=member)
            print(savings.balance)

            if loan_amount <= savings.balance:
                loan_application = LoanApplication.objects.create(
                    member_id=member,
                    loan_type=loan_type,
                    loan_amount=loan_amount,
                    loan_term_years=years,
                    loan_term_months=months,
                    loan_term_days=days,
                    total_payable=computed["totalPayable"],
                    amortization=computed["amortization"],
                    cbu=computed["cbu"],
                    insurance=computed["insurance"],
                    service_charge=computed["serviceCharge"],
                    net_proceeds=computed["releaseAmount"]
                )
            else:
                return JsonResponse({"success": False, "message": "Insufficient savings balance."})

            is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"
            if user.groups.filter(name='Bookkeeper').exists():
                context = loan_applications_data(request, ajax=is_ajax)
                html = render_to_string('loans/partials/loan_applications_table_body.html', context, request=request)
            else:
                context = member_loan_data(request, user, ajax=is_ajax)
                html = render_to_string('loans/partials/member_loan_table_body.html', context)

            return JsonResponse({
                "success": True,
                "message": f"Loan application ID {loan_application.loan_application_id} successfully created.",
                "loans": html
            })

        except Member.DoesNotExist:
            return JsonResponse({"success": False, "message": "Account number not found."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})

@login_required
def member_loan_home(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = member_loan_data(request,user, ajax=is_ajax)

    if is_ajax:
        return context
    if request.user.groups.filter(name='Member').exists():
        return render(request, 'loans/member_loan.html', context)
    

def member_loan_data(request, user, ajax=False):
    member = Member.objects.get(user_id=user)

    loans = Loan.objects.filter(member_id=member).select_related("loan_application_id")
    loan_app_ids = loans.values_list('loan_application_id__loan_application_id', flat=True)

    loan_applications = LoanApplication.objects.filter(member_id=member).exclude(
        loan_application_id__in=loan_app_ids
    )

    combined = []

    for app in loan_applications:

        if app.status in ['Approved', 'Verified', 'Pending']:
            display_status = app.status
        else:
            display_status = 'Other'
        combined.append({
            "loan_application_id": app.loan_application_id,
            "loan_amount": app.loan_amount,
            "loan_term_years": app.loan_term_years,
            "loan_term_months": app.loan_term_months,
            "loan_term_days": app.loan_term_days,
            "loan_type": app.loan_type,
            "net_proceeds": app.net_proceeds,
            "amortization": app.amortization,
            "status": app.status,
            "display_status": display_status,
        })

    for loan in loans:
        app = loan.loan_application_id

        display_status = 'Active' if loan.loan_status == 'Active' else 'Completed'
        combined.append({
            "loan_application_id": app.loan_application_id,
            "loan_amount": app.loan_amount,
            "loan_term_years": app.loan_term_years,
            "loan_term_months": app.loan_term_months,
            "loan_term_days": app.loan_term_days,
            "loan_type": app.loan_type,
            "net_proceeds": loan.loan_application_id.net_proceeds,
            "amortization": app.amortization,
            "status": loan.loan_status,
            "display_status": display_status,
        })

    status_order = {'Approved': 1, 'Verified': 2, 'Pending': 3, 'Released': 4, 'Active': 5, 'Completed': 6, 'Other': 7}
    combined.sort(key=lambda x: status_order.get(x['display_status'], 99))

    paginator = Paginator(combined, 10)
    page = paginator.get_page(request.GET.get("page"))

    context = {"page": page}

    if ajax:
        html = render_to_string("loans/partials/member_loan_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})

    return context


@login_required
def active_loans(request):
    user = request.user

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"

    context = active_loans_data(request, ajax=is_ajax)

    if is_ajax:
        return context
    
    if user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'loans/bookkeeper_active_loans.html', context)
    elif user.groups.filter(name='Admin').exists(): 
        return render(request, 'loans/admin_active_loans.html', context)
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'loans/cashier_active_loans.html', context)


"""def active_loans_data(request, ajax=False):
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

    paginator = Paginator(loans, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'loans': loans, 'page': page}

    if ajax:
        html = render_to_string("loans/partials/active_loans_table_body.html", {"page": page}, request=request)
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True ,"table_body_html": html, "pagination_html": pagination})

    return context"""


def active_loans_data(request, ajax=False):
    
    # --- 1. Retrieve Parameters ---
    search_account = request.GET.get('account', '').strip() 
    filter_status = request.GET.get('status', '').strip() 
    sort_by = request.GET.get('sort_by', '').strip()
    order = request.GET.get('order', '').strip()
    page_num = request.GET.get('page')
    
    # --- 2. Base Subquery Setup (Unpaid/Future Repayments) ---
    # Finds the soonest UNPAID repayment item from LoanRepaymentSchedule
    latest_due = LoanRepaymentSchedule.objects.filter(
        loan_id=OuterRef('pk'),
    ).exclude(
        status='Paid'
    ).order_by('due_date')

    # --- 3. Custom Status Order Priority for Sorting ---
    # This Case handles both the repayment status (status) and the final loan status (loan_status).
    status_order_case = Case(
        # Repayment Schedule Statuses (from the subquery/annotation)
        When(status='Overdue', then=Value(1)), 
        When(status='Due', then=Value(2)),
        When(status='Pending', then=Value(3)),
        When(status='Partially Paid', then=Value(4)),
        
        # Overall Loan Status (from the parent Loan model)
        When(loan_status='Completed', then=Value(5)), # <--- ADDED CONDITION
        
        default=Value(6),
        output_field=IntegerField(),
    )
    
    # --- 4. Base QuerySet and Annotation ---
    loans_qs = (
        Loan.objects
        # .filter(loan_status='Active') # Filter to only truly active loans if desired
        .select_related('member_id', 'loan_application_id')
        .annotate(
            # Annotate the fields coming from the subquery
            amount_due=Subquery(latest_due.values('amount_due')[:1]),
            due_date=Subquery(latest_due.values('due_date')[:1]),
            status=Subquery(latest_due.values('status')[:1]),
            
            # Annotate status priority for custom sorting/filtering
            status_priority=status_order_case
        )
    )

    # --- 5. APPLY SEARCH AND FILTER ---
    final_filter = Q()
    
    # A. Account Number Search
    if search_account:
        final_filter &= Q(member_id__account_number__icontains=search_account)
    
    # B. Status Filter 
    if filter_status:
        # Check against both repayment status and overall loan status
        if filter_status.lower() == 'completed':
            final_filter &= Q(loan_status__iexact='Completed')
        else:
            # Filters based on the annotated 'status' from the latest due item
            final_filter &= Q(status__iexact=filter_status)
    
    loans_qs = loans_qs.filter(final_filter)

    # --- 6. APPLY SORTING ---
    order_fields = []
    
    # Define allowed sortable fields (using the annotated field for status)
    ALLOWED_SORT_FIELDS = ['member_id__account_number', 'loan_application_id__loan_amount', 'remaining_balance', 'due_date', 'status']

    if sort_by in ALLOWED_SORT_FIELDS:
        db_sort_field = sort_by
        
        # If sorting by 'status', use the custom priority integer
        if sort_by == 'status':
            db_sort_field = 'status_priority' 
            
        sort_key = f'-{db_sort_field}' if order == 'desc' else db_sort_field
        order_fields.append(sort_key)

    # Default sort order: Use the custom status priority, then due date
    if not order_fields:
        order_fields.extend(['status_priority', 'due_date'])

    loans_qs = loans_qs.order_by(*order_fields)
    
    # --- 7. Final Values and Pagination ---
    loans = loans_qs.values(
        'loan_id',
        'loan_status',
        'member_id__account_number',
        'loan_application_id__loan_amount',
        'remaining_balance',
        'amount_due',
        'due_date',
        'status',
    )
    
    # ... (Paginator and AJAX response logic remains the same) ...
    paginator = Paginator(loans, 10)
    page = paginator.get_page(page_num)

    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'loans': loans, 
        'page': page,
        'current_query_params': current_query_params,
    }

    if ajax:
        html = render_to_string("loans/partials/active_loans_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"success": True ,"table_body_html": html, "pagination_html": pagination})

    return context

"""def cashier_approved_loans(request, ajax=False):
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
        .order_by("-application_date")
    )

    paginator = Paginator(loans, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {'loans': loans, 'page': page}

    if ajax:
        html = render_to_string("loans/partials/cashier_loan_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context"""

from django.core.paginator import Paginator
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import JsonResponse
from urllib.parse import urlencode

def cashier_approved_loans(request, ajax=False):
    
    # --- 1. Retrieve Parameters ---
    search_account = request.GET.get('account', '').strip() 
    sort_by = request.GET.get('sort_by', '').strip()     # e.g., 'member_id__account_number'
    order = request.GET.get('order', '').strip()         # 'asc' or 'desc'
    page_num = request.GET.get('page')
    
    # --- 2. Base QuerySet Setup and Filtering ---
    loans_qs = (
        LoanApplication.objects.filter(status='Approved')
        .select_related('member_id')
    )
    
    # Apply Account Number Search Filter
    if search_account:
        loans_qs = loans_qs.filter(
            Q(member_id__account_number__icontains=search_account)
        )
        
    # --- 3. APPLY SORTING (Account Number Only) ---
    order_fields = []
    
    # Only allow sorting by account number
    if sort_by == 'member_id__account_number':
        # Construct the order string: '-field_name' for descending, 'field_name' for ascending
        sort_field = f'-{sort_by}' if order == 'desc' else sort_by
        order_fields.append(sort_field)

    # Default sort order: Newest applications first
    if not order_fields:
        order_fields.append('-application_date')

    loans_qs = loans_qs.order_by(*order_fields)

    # --- 4. Final Values and Pagination ---
    loans = loans_qs.values(
        'loan_application_id',
        'member_id__account_number',
        'loan_amount',
        'loan_term_years',
        'loan_term_months',
        'loan_term_days',
        'amortization',
        'status'
    )
    
    # Paginator operates on the filtered and sorted QuerySet
    paginator = Paginator(loans, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links, retaining filters/sorts
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'loans': loans, 
        'page': page,
        'current_query_params': current_query_params, # Pass parameters for pagination links
    }

    if ajax:
        html = render_to_string("loans/partials/cashier_loan_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context


"""from django.core.paginator import Paginator
from django.db.models import Case, Value, When, IntegerField, Q, F 
from django.template.loader import render_to_string
from django.http import JsonResponse
from urllib.parse import urlencode

# NOTE: You must ensure 'LoanApplication', 'Member', and 'calculate_member_loan_risk' 
# are imported or defined elsewhere in your application.

def loan_applications_data(request, ajax=False):
    
    # --- 1. Retrieve Search and Filter Parameters ---
    # Retrieve Account Number search term (used by the 'loanSearch' input)
    search_account = request.GET.get('account', '').strip() 
    # Retrieve Status filter term (used by the 'statusFilter' select)
    filter_status = request.GET.get('status', '').strip()  
    page_num = request.GET.get('page')
    
    user = request.user
    is_bookkeeper = user.groups.filter(name='Bookkeeper').exists()
    is_admin = user.groups.filter(name='Admin').exists()

    # --- 2. Define Status Order Priority based on role ---
    if is_bookkeeper:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    elif is_admin:
        status_order_case = Case(
            When(status='Verified', then=Value(1)),
            When(status='Pending', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    else:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

    # --- 3. Base QuerySet Setup ---
    loan_applications_qs = (
        LoanApplication.objects
        .select_related('member_id', 'member_id__person_id') 
        .annotate(status_order=status_order_case)
        .order_by('status_order', '-application_date')
    )

    # --- 4. APPLY SEARCH AND FILTER ---
    final_filter = Q()
    
    # A. Apply Account Number Search
    if search_account:
        # Filter by the member's account number (case-insensitive partial match)
        final_filter &= Q(member_id__account_number__icontains=search_account)
    
    # B. Apply Status Filter
    if filter_status:
        # Filter by the selected status (case-insensitive exact match)
        final_filter &= Q(status__iexact=filter_status)

    # Apply the combined filter to the queryset
    loan_applications_qs = loan_applications_qs.filter(final_filter)

    # --- 5. Prepare final values and apply risk calculation ---
    loan_applications = loan_applications_qs.values(
        'loan_application_id',
        'member_id',
        'member_id__account_number',
        # Include person name fields if they are needed for the template, 
        # even if not searched on in this simplified version
        'member_id__person_id__first_name', 
        'member_id__person_id__surname',
        'loan_term_years',
        'loan_term_months',
        'loan_term_days',
        'loan_amount',
        'amortization',
        'status'
    )
    
    # Convert to list before iterating to prevent multiple database queries (if not done correctly)
    loan_list_with_risk = list(loan_applications) 

    for loan in loan_list_with_risk:
        # Assuming 'calculate_member_loan_risk' is a defined function
        if loan['status'] == "Pending" or loan['status'] == "Verified":
            member_id = loan['member_id']
            risk_data = calculate_member_loan_risk(member_id) 
            loan['risk_percentage'] = risk_data.get('risk_percentage')
            loan['risk_level'] = risk_data.get('risk_level')

    # --- 6. Paginate ---
    paginator = Paginator(loan_list_with_risk, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'page': page,
        'current_query_params': current_query_params,
    }

    # --- 7. AJAX Refresh or Initial Load ---
    if ajax:
        html = render_to_string("loans/partials/loan_applications_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context"""

def loan_applications_data(request, ajax=False):
    
    # --- 1. Retrieve Parameters ---
    search_account = request.GET.get('account', '').strip() 
    filter_status = request.GET.get('status', '').strip()  
    sort_by = request.GET.get('sort_by', '').strip()     # e.g., 'member_id__account_number' or 'status_priority'
    order = request.GET.get('order', '').strip()         # 'asc' or 'desc'
    page_num = request.GET.get('page')
    
    user = request.user
    # Assuming user groups are available through request.user
    is_bookkeeper = user.groups.filter(name='Bookkeeper').exists()
    is_admin = user.groups.filter(name='Admin').exists()

    # --- 2. Define Status Order Priority based on role ---
    # This calculation is annotated as 'status_order'
    if is_bookkeeper:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    elif is_admin:
        status_order_case = Case(
            When(status='Verified', then=Value(1)),
            When(status='Pending', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )
    else:
        status_order_case = Case(
            When(status='Pending', then=Value(1)),
            When(status='Verified', then=Value(2)),
            When(status='Approved', then=Value(3)),
            When(status='Released', then=Value(4)),
            When(status='Rejected', then=Value(5)),
            default=Value(6),
            output_field=IntegerField(),
        )

    # --- 3. Base QuerySet Setup and Annotation ---
    loan_applications_qs = (
        LoanApplication.objects
        .select_related('member_id', 'member_id__person_id')
        # CRITICAL: Annotate status_order BEFORE ordering by it
        .annotate(status_order=status_order_case) 
    )

    # --- 4. APPLY SEARCH AND FILTER ---
    final_filter = Q()
    if search_account:
        final_filter &= Q(member_id__account_number__icontains=search_account)
    if filter_status:
        final_filter &= Q(status__iexact=filter_status)
    
    # CRITICAL: Apply the filter to the queryset
    loan_applications_qs = loan_applications_qs.filter(final_filter)

    # --- 5. APPLY SORTING (Your provided block goes here) ---
    order_fields = []
    
    # Logic to maintain both sorts:
    # 1. Primary Sort (Based on user selection)
    if sort_by == 'member_id__account_number':
        # Account Number sort
        sort_field = f'-{sort_by}' if order == 'desc' else sort_by
        order_fields.append(sort_field)
        
        # Secondary Sort (Status Priority)
        secondary_sort = '-status_order' if order == 'desc' else 'status_order'
        order_fields.append(secondary_sort)

    elif sort_by == 'status_priority':
        # Status Priority sort
        sort_field = '-status_order' if order == 'desc' else 'status_order'
        order_fields.append(sort_field)
        
        # Secondary Sort (Account Number)
        secondary_sort = f'-member_id__account_number' if order == 'desc' else 'member_id__account_number'
        order_fields.append(secondary_sort)

    # 2. Default Sort (If no explicit sort is chosen)
    if not order_fields:
        order_fields.extend(['status_order', '-application_date'])

    # CRITICAL: Apply the final order
    loan_applications_qs = loan_applications_qs.order_by(*order_fields)
    
    # --- 6. Prepare final values and apply risk calculation ---
    loan_applications = loan_applications_qs.values(
        'loan_application_id',
        'member_id',
        'member_id__account_number',
        'member_id__person_id__first_name', 
        'member_id__person_id__surname',
        'loan_term_years',
        'loan_term_months',
        'loan_term_days',
        'loan_amount',
        'amortization',
        'status'
    )
    
    # Convert to list to apply Python-based risk calculation
    loan_list_with_risk = list(loan_applications) 

    for loan in loan_list_with_risk:
        # Assuming 'calculate_member_loan_risk' is a defined function
        if loan['status'] in ["Pending", "Verified"]:
            member_id = loan['member_id']
            # Risk calculation is done here
            risk_data = calculate_member_loan_risk(member_id) 
            loan['risk_percentage'] = risk_data.get('risk_percentage')
            loan['risk_level'] = risk_data.get('risk_level')

    # --- 7. Paginate ---
    paginator = Paginator(loan_list_with_risk, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links, retaining filters/sorts
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'page': page,
        'current_query_params': current_query_params,
    }

    # --- 8. AJAX Refresh or Initial Load ---
    if ajax:
        html = render_to_string("loans/partials/loan_applications_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"success": True, "table_body_html": html, "pagination_html": pagination})
    
    return context
    

@login_required
def loan_application_details_view(request, loan_application_id):
    loan_application_details = LoanApplication.objects.select_related('member_id', 'verifier_id', 'approver_id').get(loan_application_id=loan_application_id)
    verifier = (
        loan_application_details.verifier_id.get_full_name()
        if loan_application_details.verifier_id
        else None
    )

    approver = (
        loan_application_details.approver_id.get_full_name()
        if loan_application_details.approver_id
        else None
    )
    context = {'loan_application_details' : loan_application_details, "verifier": verifier, "approver": approver}
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
def member_loan_details_view(request, loan_application_id):
    loan_application_details = (
        LoanApplication.objects
        .select_related('member_id', 'verifier_id', 'approver_id')
        .get(loan_application_id=loan_application_id)
    )

    verifier = (
        loan_application_details.verifier_id.get_full_name()
        if loan_application_details.verifier_id else None
    )
    approver = (
        loan_application_details.approver_id.get_full_name()
        if loan_application_details.approver_id else None
    )

    # ✅ Check if the loan application already has a loan
    loan = (
        Loan.objects
        .select_related('member_id', 'released_by_id')
        .filter(loan_application_id=loan_application_id)
        .first()
    )

    # If loan exists, get schedules — otherwise skip
    schedules = []
    user_name = None
    account_number = None

    if loan:
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
        'loan_application_details': loan_application_details,
        'verifier': verifier,
        'approver': approver,
        'loan': loan,
        'user_name': user_name,
        'account_number': account_number,
        'schedules': schedules
    }

    return render(request, 'loans/member_loan_details.html', context)


@transaction.atomic
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
            member = loan_application.member_id
            if bookkeeper:
                if action == 'approve':
                    loan_application.status = 'Verified'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Verified",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) has been verified and is now under review for approval. "
                                    f"Please wait for further updates."
                    )
                elif action == 'reject':
                    loan_application.status = 'Rejected'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Rejected",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) was declined. "
                                f"For more information, please message us or contact the office."
                    )

                loan_application.verifier_id = user
                loan_application.verified_date = date.today()
                status = "Pending"
            elif admin:
                if action == 'approve':
                    loan_application.status = 'Approved'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Approved",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) has been approved. "
                                    f"Amount: ₱{loan_application.loan_amount:.2f}, Term: {format_loan_term(loan_application)}. "
                                    f"Please proceed to the cashier to finalize the release."
                    )

                elif action == 'reject':
                    loan_application.status = 'Rejected'

                    Notification.objects.create(
                        user_id=member.user_id,
                        title="Loan Application Rejected",
                        message=f"Your loan application (ID: {loan_application.loan_application_id}) was declined. "
                                f"For more information, please message us or contact the office."
                    )
                loan_application.approver_id = user
                loan_application.approved_date = date.today()
                status = "Verified"
            loan_application.save()

            # get shared data
            context = loan_applications_data(request, ajax=True)
            return context
        except LoanApplication.DoesNotExist:
            return JsonResponse({'success': False})
        except Member.DoesNotExist:
            return JsonResponse({'success': False})

@login_required
@transaction.atomic
def releasing(request):
    data = json.loads(request.body)
    loan_application_id = data.get('loan_application_id')
    user = request.user

    try:
        # Lock the loan application to prevent race conditions
        loan_application = (
            LoanApplication.objects
            .select_for_update()
            .get(loan_application_id=loan_application_id)
        )

        # 🔒 Prevent double releasing
        if loan_application.status != 'Approved':
            return JsonResponse({
                'success': False,
                'message': f"Loan has already been {loan_application.status.lower()}."
            })

        member = loan_application.member_id

        # Double-check that the loan doesn’t already exist (extra safety)
        if Loan.objects.filter(loan_application_id=loan_application).exists():
            return JsonResponse({
                'success': False,
                'message': 'This loan has already been released.'
            })

        # ✅ Proceed with loan creation
        loan = Loan.objects.create(
            member_id=member,
            loan_application_id=loan_application,
            remaining_balance=loan_application.total_payable,
            released_by_id=user
        )

        loan_days = loan_application.loan_term_days
        loan_years = loan_application.loan_term_years
        loan_months = loan_application.loan_term_months
        amortization = Decimal(loan_application.amortization)
        released_date = date.today()

        if loan_days == 100 and loan_months == 0 and loan_years == 0:
            LoanRepaymentSchedule.objects.create(
                loan_id=loan,
                due_date=released_date + relativedelta(days=loan_days),
                amount_due=loan_application.total_payable,
            )
        else:
            total_months = (loan_years * 12) + loan_months
            payment_date = released_date

            base_amortization = (loan_application.total_payable / total_months).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_rounded = base_amortization * total_months
            difference = (loan_application.total_payable - total_rounded).quantize(Decimal('0.01'))
            last_amortization = (base_amortization + difference).quantize(Decimal('0.01'))

            for i in range(total_months):
                payment_date += relativedelta(months=1)
                amount_due = last_amortization if i == total_months - 1 else amortization
                LoanRepaymentSchedule.objects.create(
                    loan_id=loan,
                    due_date=payment_date,
                    amount_due=amount_due,
                )
            
        applicable_rebates = loan.loan_application_id.loan_type in [
            'Motorcycle Loan',
            'Appliances Loan',
            'Gadget Loan'
        ]

        if applicable_rebates:
            loan.rebates = loan.loan_application_id.cbu / total_months
            loan.save()

        # Update loan application status
        loan_application.status = "Released"
        loan_application.save()

        # Update financials
        Member.objects.filter(member_id=member.member_id).update(
            insurance=F('insurance') + loan_application.insurance
        )

        Savings.objects.filter(member_id=member.member_id).update(
            balance=F('balance') + loan_application.cbu
        )

        Revenue.objects.create(
            source='Service Charge',
            member_id=member,
            amount=loan_application.service_charge / Decimal('2'),
            loan_id=loan
        )

        Expense.objects.create(
            source='Service Charge',
            member_id=member,
            amount=loan_application.service_charge / Decimal('2'),
            loan_id=loan
        )

        Funds.objects.filter(fund_name='Expenses').update(
            balance=F('balance') + (Decimal(loan_application.service_charge) / Decimal('2'))
        )

        Funds.objects.filter(fund_name='Revenue').update(
            balance=F('balance') + (Decimal(loan_application.service_charge) / Decimal('2'))
        )

        Transactions.objects.create(
            member_id=member,
            cashier_id=user,
            amount=loan_application.net_proceeds,
            transaction_type='Loan Release',
            loan_id=loan
        )

        schedules = LoanRepaymentSchedule.objects.filter(loan_id=loan).values("due_date").order_by("due_date").first()

        Notification.objects.create(
            user_id=member.user_id,
            title="Loan Released",
            message=(
                f"Your approved loan (ID: {loan.loan_id}) has been successfully released. "
                f"Amount Released: ₱{loan_application.net_proceeds:,.2f}. "
                f"Start date of repayment: {DateFormat(schedules['due_date']).format('M d, Y')}."
            )
        )

        # Return updated UI content
        context = cashier_approved_loans(request, ajax=True)
        return context

    except LoanApplication.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Loan application not found.'})
    except Member.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Member not found.'})



def run_repayment_status_update(request):
    call_command('update_repayment_status')
    return JsonResponse({'status': 'success', 'job': 'daily repayment status update executed'})

def compute_loan_details(request):
    try:
        loan_amount = Decimal(request.GET.get('loanAmount', 0))
        term = request.GET.get('loanTerm', '')

        data = compute_loan_breakdown(loan_amount, term)
        return JsonResponse({"success": True, "data": data})

    except ValueError as ve:
        return JsonResponse({"success": False, "message": str(ve)})
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})


def calculate_member_loan_risk(member_id):
    try:
        loans = Loan.objects.filter(member_id=member_id).order_by('released_date')
        if not loans.exists():
            return {
                "member_id": member_id,
                "risk_percentage": 0,
                "risk_level": "No Loan History",
            }

        schedules = LoanRepaymentSchedule.objects.filter(loan_id__in=loans)
        penalties = LoanPenalty.objects.filter(schedule_id__loan_id__in=loans)

        total_schedules = schedules.count()
        total_penalties = penalties.count()
        total_penalty_amount = penalties.aggregate(total=Sum('penalty_amount'))['total'] or Decimal('0.00')

        total_payable = LoanApplication.objects.filter(
            loan_application_id__in=loans.values_list('loan_application_id', flat=True)
        ).aggregate(total=Sum('total_payable'))['total'] or Decimal('0.00')

        # --- Risk Factors ---
        penalty_frequency_ratio = (total_penalties / total_schedules) if total_schedules > 0 else 0
        penalty_amount_ratio = (float(total_penalty_amount) / float(total_payable)) if total_payable > 0 else 0

        # Loan Growth Ratio (based on highest previous loan)
        current_loan = loans.last()
        current_amount = float(current_loan.loan_application_id.loan_amount)
        previous_max = float(
            loans.exclude(pk=current_loan.pk)
                 .aggregate(max_amt=Max('loan_application_id__loan_amount'))['max_amt'] or 0
        )
        loan_growth_ratio = max((current_amount / previous_max - 1), 0) if previous_max > 0 else 0

        # --- Weighted Risk Formula ---
        risk_score = (
            (penalty_frequency_ratio * 0.55) +
            (penalty_amount_ratio * 0.30) +
            (loan_growth_ratio * 0.15)
        )

        risk_percentage = min(round(risk_score * 100, 2), 100)

        # --- Risk Interpretation ---
        if risk_percentage < 25:
            risk_level = "Low"
        elif risk_percentage < 50:
            risk_level = "Moderate"
        elif risk_percentage < 75:
            risk_level = "High"
        else:
            risk_level = "Critical"

        return {
            "member_id": member_id,
            "risk_percentage": risk_percentage,
            "risk_level": risk_level,
            "total_loans": loans.count(),
            "total_penalties": total_penalties,
            "total_penalty_amount": float(total_penalty_amount),
            "loan_growth_ratio": round(loan_growth_ratio, 2),
        }

    except Exception as e:
        return {"error": str(e)}

def member_savings(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        savings = Savings.objects.get(member_id=member)
        member_savings = savings.balance
        return JsonResponse({"success": True, "member_savings": member_savings})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})
    except Savings.DoesNotExist:
        return JsonResponse({"success": False, "message": "Savings record not found."})
    
def check_active_loan(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        
        active_loan_exists = Loan.objects.filter(member_id=member, loan_status='Active').exists()
        print(active_loan_exists)
        return JsonResponse({"success": True, "active_loan_exists": active_loan_exists})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})

def check_active_loan_and_remaining_balance(request):
    try:
        user = request.user
        if user.groups.filter(name='Bookkeeper').exists():
            account_number = request.GET.get('accountNumber')
            member = Member.objects.get(account_number=account_number)
        elif user.groups.filter(name='Member').exists():
            member = Member.objects.get(user_id=user)
        
        active_loan = Loan.objects.filter(member_id=member, loan_status='Active').first()
        if active_loan:
            remaining_balance = active_loan.remaining_balance
            return JsonResponse({"success": True, "active_loan_exists": True, "remaining_balance": remaining_balance})
        else:
            return JsonResponse({"success": True, "active_loan_exists": False, "remaining_balance": None})
    except Member.DoesNotExist:
        return JsonResponse({"success": False, "message": "Account number not found."})