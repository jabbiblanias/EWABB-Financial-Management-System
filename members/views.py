from django.shortcuts import render
from accounts.models import Personalinfo, Membershipapplication, Spouse, Children
from .models import Member
from django.core.paginator import Paginator 
from django.http import JsonResponse
from django.template.loader import render_to_string
import json


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


def approval(request):
    if request.method == 'POST':
        user = request.user
        data = json.loads(request.body)
        application_id = data.get('applicationid')
        action = data.get('action')

        try:
            membership_application = Membershipapplication.objects.get(application_id=application_id)
            membership_application.status = 'Approved' if action == 'approve' else 'Rejected'
            membership_application.verifier_id = user
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
            html = render_to_string('members/member_table_body.html', {'membership_applications': membership_applications})
            return JsonResponse({'success': True, 'html': html})
        except Membershipapplication.DoesNotExist:
            return JsonResponse({'success': False})
        

def membership_application_details(request, application_id):
    membership_application = Membershipapplication.objects.select_related('personalinfo').get(application_id=application_id)
    context = {'membershipApplication': membership_application}
    return render(request, 'membership_application_details.html', context)
    

def members_view(request):
    members = (
            Member.objects
            .select_related('personalinfo')
            .values(
                'memberid', 
                'accountnumber'
                'personalinfo__surname', 
                'personalinfo__firstname', 
                'personalinfo__nameextension', 
                'personalinfo__middlename', 
                'personalinfo__dateofbirth', 
                'personalinfo__gender', 
                'personalinfo__civilstatus',
            )
        )
    context = {'members': members}
    return render(request, 'approved_members.html', context)


def member_details_view(request, member_id):
    member = Member.objects.select_related('personalinfo', 'membershipapplication').get(member_id=member_id)
    spouse = Spouse.objects.get(person_id=member.person_id)
    children = Children.objects.filter(person_id=member.person_id).values()
    context = {
        'member': member,
        'spouse': spouse,
        'children': children
    }
    return render(request, 'member_details.html', context)