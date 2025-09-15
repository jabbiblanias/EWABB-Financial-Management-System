from django.urls import path
from . import views


urlpatterns = [
    path('', views.member_notifications, name='notifications'),
    path("fetch-notifications/", views.fetch_notifications, name="fetch_notifications"),
    path("notifications/mark-read/", views.mark_notification_read, name="mark_notification_read"),
]
