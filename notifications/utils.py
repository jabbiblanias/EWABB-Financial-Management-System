import random
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from .models import EmailOTP
from datetime import date
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
import dns.resolver


def is_email_valid(email):
    """Check if email has valid format and domain MX records."""
    try:
        # Format check
        validate_email(email)

        # Domain MX record check
        domain = email.split('@')[1]
        dns.resolver.resolve(domain, 'MX')  # will raise if no MX
        return True
    except (ValidationError, dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False
    

def registration_otp(first_name, email):
    if not is_email_valid(email):
        # 🚨 Invalid email → skip OTP and return False
        return False  
    
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