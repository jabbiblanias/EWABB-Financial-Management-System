from django.urls import path
from . import views

urlpatterns = [
    path('', views.loan_application_view, name='loanApplicationView'),
    path('<int:loan_application_id>/details/', views.loan_application_details, name='loanApplicationDetails'),
]