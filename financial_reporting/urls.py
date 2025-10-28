from django.urls import path
from . import views

urlpatterns = [
    path("", views.member_loan_report, name="financial_report"),
    path("monthly-report/details/<int:report_id>/", views.monthly_report_details, name="monthly_report_details"),
    path("dividend-report/details/<int:report_id>/", views.dividend_report_details, name="dividend_report_details"),
    path("monthly-report/new/", views.monthly_report, name="monthly_report"),
    path("dividend-report/new/", views.dividend_report, name="dividend_report"),
    path("monthly/submit/", views.submit_monthly_report, name="submit_monthly_report"),
    path("dividend/submit/", views.submit_dividend_report, name="submit_dividend_report"),
    path('monthlyPdf/<int:report_id>/', views.monthly_pdf_report_export, name ='monthly_pdf'),
    path('dividendPdf/<int:report_id>/', views.dividend_pdf_report_export, name ='dividend_pdf'),
    path("monthly/csv/<int:report_id>/", views.monthly_report_csv, name="monthly_csv"),
    path("dividend/csv/<int:report_id>/", views.dividend_report_csv, name="dividend_csv"),
]