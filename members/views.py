from django.shortcuts import render
from accounts.models import Personalinfo, Membershipapplication, Spouse, Children
from members.models import Savings
from .models import Member
from django.core.paginator import Paginator 
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required
import json
from django.contrib.auth.models import Group
from django.db import transaction



@login_required
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
    )
    '''book_paginator = Paginator(membership_applications, 10)

    page_num = request.GET.get('page')

    page = book_paginator.get_page(page_num)'''
    context = {
        'membershipApplications': membership_applications
        #'page': page
    }
    return render(request, 'members/membership_applications.html', context)


@transaction.atomic
def approval(request):
    if request.method == 'POST':
        approver = request.user
        data = json.loads(request.body)
        application_id = data.get('applicationid')
        action = data.get('action')
        account_number = data.get('account_number')

        try:
            membership_application = Membershipapplication.objects.get(application_id=application_id) 
            if action == 'approve':
                member = Member.objects.create(
                    user_id=membership_application.user_id,
                    person_id=membership_application.person_id,
                    account_number=account_number
                )
                membership_application.status = 'Approved'
                membership_application.verifier_id = approver
                membership_application.save()

                # Automatically assign user to 'Member' group
                member_group = Group.objects.get(name='Member')
                membership_application.user_id.groups.add(member_group)

                Savings.objects.create(member_id=member)
            else:
                membership_application.status = 'Rejected'
                membership_application.verifier_id = approver
                membership_application.save()

            # Re-fetch and re-render the table body
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
            html = render_to_string('members/membership_table_body.html', {'membershipApplications': membership_applications})
            return JsonResponse({'success': True, 'html': html})
        except Membershipapplication.DoesNotExist:
            return JsonResponse({'success': False})
        

def membership_application_details(request, application_id):
    membership_application = Membershipapplication.objects.select_related('person_id').get(application_id=application_id)
    context = {'membership_application': membership_application}
    return render(request, 'members/membership_application_details.html', context)
    

def members_view(request):
    members = (
            Member.objects
            .select_related('person_id')
            .values(
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
        )
    context = {'members': members}
    return render(request, 'members/approved_members.html', context)


def member_details_view(request, member_id):
    member = Member.objects.select_related('person_id').get(member_id=member_id)
    # Handle spouse safely
    try:
        spouse = Spouse.objects.get(person_id=member.person_id)
    except Spouse.DoesNotExist:
        spouse = None

    # Handle children safely
    children = Children.objects.filter(person_id=member.person_id)  # returns queryset (empty if none)
    context = {
        'member': member,
        'spouse': spouse,
        'children': children
    }
    return render(request, 'members/member_details.html', context)