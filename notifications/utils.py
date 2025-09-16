import random
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import EmailOTP
from datetime import date

def registration_otp(first_name, email):
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    otp_code = EmailOTP.objects.create(email=email, otp_code=code)

    today_date = date.today()

    subject = "Your OTP for Account Verification"
    from_email = "noreply.ewabb@gmail.com"
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