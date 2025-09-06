from django.urls import path
from . import views

urlpatterns = [
    path('', views.transaction_view, name="transactions"),
    path('save_transaction/', views.transactions, name="save_transaction"),
]