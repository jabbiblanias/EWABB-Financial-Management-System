from django.urls import path
from . import views

urlpatterns = [
    path('', views.member_loan_home, name='loans'),
    path('loan-applications/', views.loan_application_view, name='loan_applications'),
    path('loan-applications/approval/', views.approving_loan, name='loan_approval'),
    path('approved-applications/', views.approved_loans, name='approved_loans'),
    path('<int:loan_application_id>/details/', views.loan_application_details_view, name='loanApplicationDetails'),
]