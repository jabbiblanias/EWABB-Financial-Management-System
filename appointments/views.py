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
        context = member_appointment_data(user)
        return render(request, 'appointments/member_appointment.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        context = appointment_request()
        return render(request, 'appointments/bookkeeper_appointment.html', context)
    

def member_appointment_data(user):
    member_id = Member.objects.get(user_id=user)
    appointments = (
        Appointments.objects.
        filter(member_id=member_id)
        .values(
            "appointment_id",
            "appointment_date", 
            "appointment_time", 
            "appointment_type", 
            "status"
        )
    )
    context = {"appointments": appointments}
    return context


def appointment_request():
    appointments = (
        Appointments.objects
        .select_related("member_id__person_id")  # follow the relation
        .filter(status="Pending")
        .values(
            "appointment_id",
            "member_id__account_number",
            "member_id__person_id__first_name",
            "member_id__person_id__middle_name",
            "member_id__person_id__surname",
            "member_id__person_id__name_extension",
            "appointment_type",
            "appointment_date",
            "appointment_time",
        )
    )
    return {"appointments": appointments}


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
    

def update_appointment(request):
    user = request.user
    data = json.loads(request.body)
    selected_date = data.get('date')
    time = data.get('time')
    appointment_type = data.get('appointmentType')

    member_id = Member.objects.get(user_id=user)

    date_obj = parser.parse(selected_date).date()

    appointment = Appointments.objects.get(appointment_date=selected_date)

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
    try:
        user = request.user
        member_id = Member.objects.get(user_id=user.id)
        
        # We need to handle potential missing GET parameters
        year_str = request.GET.get("year")
        month_str = request.GET.get("month")

        if not year_str or not month_str:
            return JsonResponse({'success': False, 'message': 'Missing year or month parameter.'}, status=400)

        year = int(year_str)
        month = int(month_str)

        # Fetch appointments for the specified year and month
        appointments_query = Appointments.objects.filter(
            member_id=member_id,
            appointment_date__year=year,
            appointment_date__month=month
        ).values("appointment_date", "appointment_time", "appointment_type")

        # Map appointment types to colors (these match the frontend)
        type_colors = {
            "Consultation": "bg-blue-300",
            "Follow-up": "bg-green-300",
            "Cashier Transaction": "bg-purple-300",
        }

        # Format the data into a dictionary with date strings as keys
        formatted_appointments = {}
        for appt in appointments_query:
            # Convert date object to a "YYYY-M-D" string
            date_key = f"{appt['appointment_date'].year}-{appt['appointment_date'].month}-{appt['appointment_date'].day}"
            formatted_appointments[date_key] = {
                "time": appt['appointment_time'],
                "type": appt['appointment_type'],
                "color": type_colors.get(appt['appointment_type'], "bg-gray-500")
            }

        return JsonResponse({'success': True, 'appointments': formatted_appointments})
    except (ValueError, Member.DoesNotExist) as e:
        # Catch errors like invalid year/month format or non-existent member
        print(f"Error in member_appointments view: {e}")
        return JsonResponse({'success': False, 'message': 'An error occurred. Please try again.'}, status=500)
    #return JsonResponse({'success': True, 'appointments': appointments})



    
