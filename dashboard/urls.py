from django.urls import path
from . import views

urlpatterns = [   
    path('', views.dashboard_view, name='dashboard'),
    path('cashier-status/', views.cashier_status, name='get_cashier_status'),
    path('update-status/', views.update_status, name='update_status'),
    path('cashier-availability/', views.cashier_transaction_availablity, name='cashier_availability'),
]
