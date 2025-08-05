from django.urls import path
from . import views

urlpatterns = [
    path("", views.financial_report_view, name="financial_report"),
    path("submit/", views.submit_financial_report, name="submit_financial_report"),
]