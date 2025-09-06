from django.shortcuts import render 
from django.contrib.auth.decorators import login_required
from members.models import Member
from members.models import Savings
import json

@login_required
def dashboard_view(request):
    user = request.user
    
    if user.groups.filter(name='Admin').exists():
        return render(request, 'dashboard/admin.html')
    elif user.groups.filter(name='Member').exists():
        context = member_dashboard_data(user)
        return render(request, 'dashboard/member.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        context = bookkeeper_dashboard_data()
        return render(request, 'dashboard/bookkeeper.html', context)
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'dashboard/cashier.html')
    

def member_dashboard_data(user):
    daily_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_data = [12, 19, 3, 5, 2, 3, 7]

    weekly_labels = ["Week 1", "Week 2", "Week 3", "Week 4"]
    weekly_data = [150, 200, 180, 220]

    yearly_labels = ["2021", "2022", "2023", "2024"]
    yearly_data = [1200, 1500, 1700, 1600]

    balance = (
        Savings.objects
        .select_related("member_id__user_id")
        .get(member_id__user_id=user)
        .balance
    )
    context = {
        "daily_labels": json.dumps(daily_labels),
        "daily_data": json.dumps(daily_data),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_data": json.dumps(weekly_data),
        "yearly_labels": json.dumps(yearly_labels),
        "yearly_data": json.dumps(yearly_data),
        "balance":  balance
    }
    return context


def bookkeeper_dashboard_data():
    total_members = Member.objects.count()
    context = {"total_members": total_members}
    return context
    
