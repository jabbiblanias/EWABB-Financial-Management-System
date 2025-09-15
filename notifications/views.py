from django.shortcuts import render
from .models import Notification
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

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


@login_required
def fetch_notifications(request):
    notifications = (
        Notification.objects
        .filter(user_id=request.user)
        .order_by('-created_at')[:5]
    )

    data = [
        {
            "notification_id": n.notification_id,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%b %d, %Y %I:%M %p"),
        }
        for n in notifications
    ]
    return JsonResponse({"notifications": data})


def mark_notification_read(request):
    try:
        body = json.loads(request.body)
        notif_id = body.get("notification_id")

        notification = Notification.objects.get(notification_id=notif_id, user_id=request.user)
        notification.is_read = True
        notification.save()

        return JsonResponse({"success": True})
    except Notification.DoesNotExist:
        return JsonResponse({"success": False, "error": "Notification not found"}, status=404)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)