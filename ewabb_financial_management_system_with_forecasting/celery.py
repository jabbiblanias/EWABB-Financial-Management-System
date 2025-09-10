import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ewabb_financial_management_system_with_forecasting.settings')

app = Celery('ewabb_financial_management_system_with_forecasting')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()