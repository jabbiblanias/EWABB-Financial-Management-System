from django.shortcuts import render
from .models import Notification

# Create your views here.
def member_notifications(request):
    notifications = (
        Notification.objects
        .filter(user_id=request.user)
        .values(
            'notification_id',
            'title',
            'message',
            'is_read',
            'created_at'
        )
        .order_by('-created_at')
    )
    context = {"notifications" : notifications}
    return render(request, 'notifications/notification.html', context)
