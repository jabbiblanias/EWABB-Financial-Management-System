from django.shortcuts import render 
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_view(request):
    user = request.user
    if user.groups.filter(name='Admin').exists():
        return render(request, 'dashboard/admin.html')
    elif user.groups.filter(name='Member').exists():
        return render(request, 'dashboard/member.html')
    elif user.groups.filter(name='Bookkeeper').exists():
        return render(request, 'dashboard/bookkeeper.html')
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'dashboard/cashier.html')