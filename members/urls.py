from django.urls import path
from . import views


urlpatterns = [
    path('membership-applications/', views.membership_application_view, name='membershipApplication'),
    path('membership-applications/approval/', views.approval, name='approval'),
    path('membership-applications/details/<int:application_id>/', views.membership_application_details, name='membershipApplicationDetails'),
    path('approved-members/', views.members_view, name='members'),
    path('approved-members/details/<int:member_id>/', views.member_details_view, name='memberDetails'),
]