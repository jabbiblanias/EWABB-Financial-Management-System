from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_page, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/1/', views.register_step1, name='register1'),
    path('register/2/', views.register_step2, name='register2'),
    path('register/3/', views.register_step3, name='register3'),
    path('register/3/', views.register_step3, name='register3'),
    path('register/verify/', views.registration_otp_verification_view, name='register_verify'),
    path('register/complete/', views.success_view, name='complete_registration'),
]