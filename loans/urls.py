from django.urls import path
from . import views

urlpatterns = [
    path('', views.member_loan_home, name='loans'),
    path('loan-applications/', views.loan_application_view, name='loan_applications'),
    path('compute-loan/', views.compute_loan_details, name='compute_loan_details'),
    path('apply-loan/', views.apply_loan, name='apply_loan'),
    path('member-savings/', views.member_savings, name='get_member_savings'),
    path('loan-applications/approval/', views.approving_loan, name='loan_approval'),
    path('loan-applications/release/', views.releasing, name='loan_release'),
    path('active-loans/', views.active_loans, name='active_loans'),
    path('loan-applications/details/<int:loan_application_id>/', views.loan_application_details_view, name='loanApplicationDetails'),
    path('active-loans/details/<int:loan_id>/', views.loan_details_view, name='loanDetails'),
    path('repayments-status-update/', views.run_repayment_status_update, name="repayment_status_update"),
    path('check-active-loans/', views.check_active_loan, name='check_active_loan')
]