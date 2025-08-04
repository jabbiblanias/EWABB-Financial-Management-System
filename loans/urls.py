from django.urls import path
from . import views

urlpatterns = [
    path('', views.loan_application_view, name='loanApplicationView'),
    path('apply/', views.apply_loan, name='applyLoan'),
    path('<int:loan_application_id>/details/', views.loan_application_details_view, name='loanApplicationDetails'),
]