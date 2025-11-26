from django.shortcuts import redirect, render
from accounts.models import Personalinfo, Membershipapplication, Spouse, Children, EmergencyContact
from members.models import Savings
from .models import Member
from django.core.paginator import Paginator 
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
import json
from django.contrib.auth.models import Group
from django.db import transaction
from notifications.utils import email_approved, email_rejected
from django.contrib.auth.models import User
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat


"""@login_required
def membership_application_view(request):
    membership_applications = (
        Membershipapplication.objects
        .select_related('person_id')
        .filter(status='Pending')
        .values(
            'application_id', 
            'person_id__surname', 
            'person_id__first_name', 
            'person_id__name_extension', 
            'person_id__middle_name', 
            'person_id__date_of_birth', 
            'person_id__gender', 
            'person_id__civil_status'
        )
        .order_by('application_id')
    )
    paginator = Paginator(membership_applications, 10)

    page_num = request.GET.get('page')

    page = paginator.get_page(page_num)
    context = {
        'membershipApplications': membership_applications,
        'page': page
    }

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    if is_ajax:
        html = render_to_string("members/partials/membership_table_body.html", {"page": page})
        pagination = render_to_string("partials/pagination.html", {"page": page})
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})
    
    return render(request, 'members/membership_applications.html', context)"""

from django.core.paginator import Paginator
from django.db.models import Q, Value, CharField, F
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from urllib.parse import urlencode

@login_required
def membership_application_view(request):
    
    # --- 1. Retrieve Parameters ---
    # We will use 'search' for the name search parameter
    search_term = request.GET.get('account', '').strip() 
    sort_by = request.GET.get('sort_by', '').strip()
    order = request.GET.get('order', '').strip()
    page_num = request.GET.get('page')
    
    # --- 2. Base QuerySet Setup and Annotation ---
    membership_applications_qs = (
        Membershipapplication.objects
        .select_related('person_id')
        .filter(status='Pending')
        # 1. ANNOTATE: Create searchable fields combining first and last name
        .annotate(
            full_name_spaced=Concat(
                'person_id__first_name', Value(' '), 'person_id__surname',
                output_field=CharField()
            ),
            full_name_comma=Concat(
                'person_id__surname', Value(', '), 'person_id__first_name',
                output_field=CharField()
            )
        )
    )

    if search_term:
        final_filter = (
            
            # 2. SEARCH: Search the concatenated fields for the full name
            Q(full_name_spaced__icontains=search_term) | # Supports "Grace Moret"
            Q(full_name_comma__icontains=search_term) |  # Supports "Moret, Grace"
            
            # 3. FALLBACK: Search individual fields (for single word or partial matching)
            Q(person_id__surname__icontains=search_term) |
            Q(person_id__first_name__icontains=search_term)
        )
        
        membership_applications_qs = membership_applications_qs.filter(final_filter)
        
    # --- 4. APPLY SORTING ---
    order_fields = []
    
    # Define allowed sortable fields
    ALLOWED_SORT_FIELDS = ['application_id', 'person_id__first_name']

    if sort_by in ALLOWED_SORT_FIELDS:
        db_sort_field = sort_by
        
        # Construct the order string: '-field_name' for descending, 'field_name' for ascending
        sort_field = f'-{db_sort_field}' if order == 'desc' else db_sort_field
        order_fields.append(sort_field)

    # Default sort order: Newest applications first, then by Surname
    if not order_fields:
        order_fields.extend(['-application_id', 'person_id__first_name'])

    membership_applications_qs = membership_applications_qs.order_by(*order_fields)

    # --- 5. Final Values and Pagination ---
    membership_applications = membership_applications_qs.values(
        'application_id', 
        'person_id__surname', 
        'person_id__first_name', 
        'person_id__name_extension', 
        'person_id__middle_name', 
        'person_id__date_of_birth', 
        'person_id__gender', 
        'person_id__civil_status'
    )
    
    paginator = Paginator(membership_applications, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links, retaining filters/sorts
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'membershipApplications': membership_applications,
        'page': page,
        'current_query_params': current_query_params,
    }

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    if is_ajax:
        html = render_to_string("members/partials/membership_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})
    
    return render(request, 'members/membership_applications.html', context)

@transaction.atomic
def approval(request):
    if request.method == 'POST':
        approver = request.user
        data = json.loads(request.body)
        application_id = data.get('applicationid')
        action = data.get('action')

        try:
            # Lock the row for this transaction
            membership_application = (
                Membershipapplication.objects
                .select_for_update()
                .get(application_id=application_id)
            )

            # Prevent double approval/rejection
            if membership_application.status != 'Pending':
                return JsonResponse({
                    'success': False,
                    'message': f"Application already {membership_application.status.lower()}."
                })

            account_number = None

            if action == 'approve':
                member = Member.objects.create(
                    user_id=membership_application.user_id,
                    person_id=membership_application.person_id
                )
                membership_application.status = 'Approved'
                membership_application.verifier_id = approver
                membership_application.save()

                # Assign to 'Member' group
                member_group = Group.objects.get(name='Member')
                membership_application.user_id.groups.add(member_group)

                Savings.objects.create(member_id=member)
                account_number = member.account_number

                # Notify
                personal_info = membership_application.person_id
                user = membership_application.user_id
                email_approved(personal_info.first_name, user.email)

            elif action == 'reject':
                membership_application.status = 'Rejected'
                membership_application.verifier_id = approver
                membership_application.save()

                personal_info = membership_application.person_id
                user = membership_application.user_id
                email_rejected(personal_info.first_name, user.email)

            # Refresh table
            membership_applications = (
                Membershipapplication.objects
                .select_related('person_id')
                .filter(status='Pending')
                .values(
                    'application_id', 
                    'person_id__surname', 
                    'person_id__first_name', 
                    'person_id__name_extension', 
                    'person_id__middle_name', 
                    'person_id__date_of_birth', 
                    'person_id__gender', 
                    'person_id__civil_status'
                )
            )
            html = render_to_string(
                'members/partials/membership_table_body.html',
                {'membershipApplications': membership_applications}
            )
            return JsonResponse({'success': True, 'html': html, 'account_number': account_number})

        except Membershipapplication.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Application not found.'})
        

def membership_application_details(request, application_id):
    application = Membershipapplication.objects.select_related('person_id').get(application_id=application_id)
    # Handle spouse safely
    try:
        spouse = Spouse.objects.get(person_id=application.person_id)
    except Spouse.DoesNotExist:
        spouse = None

    # Handle children safely
    children = Children.objects.filter(person_id=application.person_id)  # returns queryset (empty if none)

    try:
        emergency_contact = EmergencyContact.objects.get(person_id=application.person_id)
    except EmergencyContact.DoesNotExist:
        emergency_contact = None

    context = {
        'application': application,
        'spouse': spouse,
        'children': children,
        'emergency_contact': emergency_contact
    }
    return render(request, 'members/membership_application_details.html', context)
    

from django.core.paginator import Paginator
from django.db.models import Q
from django.template.loader import render_to_string
from django.http import JsonResponse
from urllib.parse import urlencode

def members_view(request):
    
    # --- 1. Retrieve Parameters ---
    # We will use 'search' for the combined search input
    search_term = request.GET.get('account', '').strip() 
    sort_by = request.GET.get('sort_by', '').strip()
    order = request.GET.get('order', '').strip()
    page_num = request.GET.get('page')
    
    # --- 2. Base QuerySet Setup ---
    members_qs = (
        Member.objects
        .select_related('person_id')
        # 1. ANNOTATE: Create searchable fields combining first and last name
        .annotate(
            full_name_spaced=Concat(
                'person_id__first_name', Value(' '), 'person_id__surname',
                output_field=CharField()
            ),
            full_name_comma=Concat(
                'person_id__surname', Value(', '), 'person_id__first_name',
                output_field=CharField()
            )
        )
    )

    if search_term:
        final_filter = (
            Q(account_number__icontains=search_term) |
            
            # 2. SEARCH: Search the concatenated fields for the full name
            Q(full_name_spaced__icontains=search_term) | # Supports "Grace Moret"
            Q(full_name_comma__icontains=search_term) |  # Supports "Moret, Grace"
            
            # 3. FALLBACK: Search individual fields (for single word or partial matching)
            Q(person_id__surname__icontains=search_term) |
            Q(person_id__first_name__icontains=search_term)
        )
        
        members_qs = members_qs.filter(final_filter)
        
    # --- 4. APPLY SORTING ---
    order_fields = []
    
    # Define allowed sortable fields
    ALLOWED_SORT_FIELDS = ['account_number', 'person_id__first_name']

    if sort_by in ALLOWED_SORT_FIELDS:
        db_sort_field = sort_by
        
        # Construct the order string: '-field_name' for descending, 'field_name' for ascending
        sort_field = f'-{db_sort_field}' if order == 'desc' else db_sort_field
        order_fields.append(sort_field)

    # Default sort order: By Member ID
    if not order_fields:
        order_fields.append('member_id')

    members_qs = members_qs.order_by(*order_fields)

    # --- 5. Final Values and Pagination ---
    members = members_qs.values(
        'member_id', 
        'account_number',
        'person_id__surname', 
        'person_id__first_name', 
        'person_id__name_extension', 
        'person_id__middle_name', 
        'person_id__date_of_birth', 
        'person_id__gender', 
        'person_id__civil_status',
    )
    
    paginator = Paginator(members, 10)
    page = paginator.get_page(page_num)

    # Calculate query parameters for pagination links, retaining filters/sorts
    get_params = request.GET.copy()
    if 'page' in get_params:
        del get_params['page']
        
    current_query_params = '&' + urlencode(get_params) if get_params else ''

    context = {
        'members': members, 
        'page': page,
        'current_query_params': current_query_params, # Used for pagination links
    }

    is_ajax = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest" \
              or request.META.get("HTTP_X_REQUESTED_WITH", "").lower() == "xmlhttprequest"
    
    if is_ajax:
        # Pass the request object to render_to_string for access to context processors/token
        html = render_to_string("members/partials/members_table_body.html", context, request=request)
        pagination = render_to_string("partials/pagination.html", context)
        return JsonResponse({"table_body_html": html, "pagination_html": pagination})
    
    return render(request, 'members/approved_members.html', context)


def member_details(request, member_id):
    member = Member.objects.select_related('person_id', 'user_id').get(member_id=member_id)
    # Handle spouse safely
    try:
        spouse = Spouse.objects.get(person_id=member.person_id)
    except Spouse.DoesNotExist:
        spouse = None

    # Handle children safely
    children = Children.objects.filter(person_id=member.person_id)  # returns queryset (empty if none)

    try:
        emergency_contact = EmergencyContact.objects.get(person_id=member.person_id)
    except EmergencyContact.DoesNotExist:
        emergency_contact = None

    context = {
        'member': member,
        'spouse': spouse,
        'children': children,
        'emergency_contact': emergency_contact
    }
    return render(request, 'members/member_details.html', context)

@login_required
def toggle_member_status(request, member_id):
    if request.method == "POST":
        member = Member.objects.get(member_id=member_id)
        member.user_id.is_active = not member.user_id.is_active
        member.user_id.save()

        return JsonResponse({
            "status": "success",
            "is_active": member.user_id.is_active
        })

    return JsonResponse({"status": "error"})