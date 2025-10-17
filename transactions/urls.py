from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_view, name="transactions"),
    path('save_transaction/', views.transactions, name="save_transaction"),
    path('loan_balance/', views.balance, name="balance"),
    path('passbook_print/', views.passbook_print, name='print_passbook'),
]