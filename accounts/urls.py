from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_page, name='home'),
    path('login/', views.login_view, name='login'),
    path('login/verification', views.login_verification, name='login_verification'),
    path('profile/', views.profile_information, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('register/1/', views.register_step1, name='register1'),
    path('register/2/', views.register_step2, name='register2'),
    path('register/3/', views.register_step3, name='register3'),
    path('check_email/', views.check_email, name='check_email'),
    path('check_username/', views.check_username, name='check_username'),
    path('register/verify/', views.registration_otp_verification_view, name='register_verify'),
    path('update-timer/', views.update_timer, name='update_timer'),
    path('resend/', views.resend_otp, name='resend'),
    path('register/complete/', views.success_view, name='complete_registration'),
    path('fetch-profile/', views.fetch_profile, name='fetch_profile'),
    path('search-member/', views.search_member, name='search-member'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/verification', views.password_reset_verification, name='password_reset_verification'),
    path('password-reset/', views.password_reset, name='password_reset'),
]