"""
WSGI config for ewabb_financial_management_system_with_forecasting project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ewabb_financial_management_system_with_forecasting.settings')

app = get_wsgi_application()
