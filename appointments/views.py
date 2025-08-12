from django.shortcuts import render

def appointments_view(request):
    user = request.user
    if user.groups.filter(name='Admin').exists():
        return render(request, 'appointments/admin_appointment.html')
    elif user.groups.filter(name='Member').exists():
        return render(request, 'appointments/member_appointment.html')
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'appointments/bookkeeper_appointment.html')
