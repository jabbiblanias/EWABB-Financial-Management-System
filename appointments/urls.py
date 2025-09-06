from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointments_view, name="appointments"),
    path('save/', views.save_appointment, name="save_appointment"),
    path('member-appointments/', views.member_appointment, name="member_appointments"),
]