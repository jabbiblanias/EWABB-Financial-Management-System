from django.urls import path
from . import views

urlpatterns = [
    path("", views.member_loan_report, name="financial_report"),
    path("details/<int:report_id>/", views.report_details, name="report_details"),
    path("new/", views.generate_report, name="new_report"),
    path("submit/", views.submit_financial_report, name="submit_report"),
    path("pdf/", views.pdf_report, name="pdf_report"),
    #path('createPdf/<int:report_id>/', views.pdf_report_export, name ='create-pdf'),
]