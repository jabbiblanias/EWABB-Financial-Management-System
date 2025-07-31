from django.shortcuts import render
from accounts.models import Personalinfo, Membershipapplication, Spouse, Children
from .models import Member

def membership_application_view(request, application_id, action):
    if request.method == 'POST':
        user = request.user
        membership_application = Membershipapplication.objects.get(application_id=application_id)
        if action == 'approve':
            membership_application.status = 'Approved'
        elif action == 'reject':
            membership_application.status = 'Rejected'
        membership_application.verifier_id = user
        membership_application.save()

    membership_applications = (
            Membershipapplication.objects
            .select_related('personalinfo')
            .filter(status='Pending')
            .values(
                'membershipapplicationid', 
                'personalinfo__surname', 
                'personalinfo__firstname', 
                'personalinfo__nameextension', 
                'personalinfo__middlename', 
                'personalinfo__dateofbirth', 
                'personalinfo__gender', 
                'personalinfo__civilstatus'
            )
        )
    context = {'membershipApplications': membership_applications}
    return render(request, 'membership_applications.html', context)

def membership_application_details(request, application_id):
    if request.method == 'GET':
        membersship_application = Membershipapplication.objects.select_related('personalinfo').get(application_id=application_id)
        context = {'membershipApplication': membersship_application}
        return render(request, 'membership_application_details.html', context)
    

def members_view(request):
    if request.method == 'GET':
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
    if request.method == 'GET':
        member = Member.objects.select_related('personalinfo', 'membershipapplication').get(member_id=member_id)
        spouse = Spouse.objects.get(person_id=member.person_id)
        children = Children.objects.filter(person_id=member.person_id).values()
        context = {
            'member': member,
            'spouse': spouse,
            'children': children
        }
        return render(request, 'member_details.html', context)