from django.shortcuts import render
from .models import Appointments
import json
from django.http import JsonResponse
from members.models import Member
from datetime import date
from dateutil import parser
from django.contrib.auth.decorators import login_required
from django.utils.dateformat import DateFormat


@login_required
def appointments_view(request):
    user = request.user

    if user.groups.filter(name='Admin').exists():
        return render(request, 'appointments/admin_appointment.html')
    elif user.groups.filter(name='Member').exists():
        '''appointments = Appointments.objects.filter(member__user=user)

        # convert dates to string (YYYY-MM-DD)
        appointment_dates = [DateFormat(appt.date).format('Y-m-d') for appt in appointments]'''
        return render(request, 'appointments/member_appointment.html')
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'appointments/bookkeeper_appointment.html')

def calendar_view(request, year, month):
    user = request.user
    appointments = Appointments.objects.filter(
        member__user=user,
        date__year=year,
        date__month=month
    ).values('date', 'appointment_type')

    return JsonResponse({'appointments': list(appointments)})
def save_appointment(request):
    user = request.user
    data = json.loads(request.body)
    selected_date = data.get('date')
    time = data.get('time')
    appointment_type = data.get('appointmentType')

    member_id = Member.objects.get(user_id=user)

    date_obj = parser.parse(selected_date).date()

    if date_obj > date.today() and selected_date and time and appointment_type:   
        Appointments.objects.create(
            member_id=member_id,
            appointment_date=selected_date,
            appointment_time=time,
            appointment_type=appointment_type
        )
        message = "Appointment has successfully been created."
        return JsonResponse({'success': True, 'message': message})
    else:
        message = "Appointment has failed to save."
        return JsonResponse({'success': False ,'message': message})

@login_required
def member_appointment(request):
    user = request.user
    member_id = Member.objects.get(user_id=user)
    appointments = Appointments.objects.filter(memberid=member_id)
    return JsonResponse({'success': True, 'appointments': appointments})



    
