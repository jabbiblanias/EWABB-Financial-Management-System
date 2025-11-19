from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_view, name="transactions"),
    path('save_transaction/', views.transactions, name="save_transaction"),
    path('loan_balance/', views.balance, name="balance"),
    path('passbook/<str:account_number>/', views.passbook_print, name='passbook'),
    path('member-ledger/<int:member_id>/', views.member_details, name='member_ledger'),
]