from django.urls import path
from . import views


urlpatterns = [
    path('', views.member_notifications, name='notifications'),
    path("fetch-notifications/", views.fetch_notifications, name="fetch_notifications"),
    path("notifications/mark-read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/selected-mark-read/", views.selected_mark_notification_read, name="selected_mark_notification_read"),
    path("notifications/check-unread/", views.check_unread_notifications, name="check_unread_notifications"),
    
]
