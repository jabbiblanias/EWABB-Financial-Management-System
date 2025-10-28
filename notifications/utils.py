import random
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import EmailOTP
from datetime import date
from django.utils import timezone
from django.conf import settings
from django.urls import reverse


def otp(first_name, email):
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    EmailOTP.objects.create(email=email, otp_code=code)

    today_date = timezone.localdate()

    subject = "Your OTP for Account Verification"
    from_email = settings.EMAIL_HOST_USER
    to_email = [email]

    context = {
        "first_name": first_name,
        "otp": code,
        "current_year": today_date.year
    }

    # Render plain text + HTML versions
    text_content = render_to_string("notifications/otp_email.txt", context)
    html_content = render_to_string("notifications/otp_email.html", context)

    # Create email with both versions
    mail = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    mail.attach_alternative(html_content, "text/html")  # attach HTML version
    mail.send()

def email_approved(first_name, email):
    today_date = timezone.localdate()
    login_url = f"http://127.0.0.1:8000{reverse('login')}"

    subject = "EWABB Membership Approved"
    from_email = settings.EMAIL_HOST_USER
    to_email = [email]

    context = {
        "first_name": first_name,
        "current_year": today_date.year
    }

    # Render plain text + HTML versions
    text_content = render_to_string("notifications/approved_email.txt", context)
    html_content = render_to_string("notifications/approved_email.html", context)

    # Create email with both versions
    mail = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    mail.attach_alternative(html_content, "text/html")  # attach HTML version
    mail.send()

def email_rejected(first_name, email):
    today_date = timezone.localdate()

    subject = "EWABB Membership Rejected"
    from_email = settings.EMAIL_HOST_USER
    to_email = [email]

    context = {
        "first_name": first_name,
        "current_year": today_date.year
    }

    # Render plain text + HTML versions
    text_content = render_to_string("notifications/rejected_email.txt", context)
    html_content = render_to_string("notifications/rejected_email.html", context)

    # Create email with both versions
    mail = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    mail.attach_alternative(html_content, "text/html")  # attach HTML version
    mail.send()