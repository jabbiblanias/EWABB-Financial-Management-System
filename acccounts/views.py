from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context
from django.contrib import messages

def login_view(request):
    error = None
    if request.method == 'POST':
        identifier = request.POST.get('identifier')
        password = request.POST.get('password')

        # Find user by username or email
        try:
            user_obj = User.objects.get(username=identifier)
        except User.DoesNotExist:
            try:
                user_obj = User.objects.get(email=identifier)
            except User.DoesNotExist:
                user_obj = None

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')

        error = "Invalid username/email or password"

    return render(request, 'accounts/login.html', {'error': error})


@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('login')