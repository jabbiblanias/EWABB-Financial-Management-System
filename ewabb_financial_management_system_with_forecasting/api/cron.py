import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ewabb_financial_management_system_with_forecasting.settings")
django.setup()

from django.core.management import call_command

def handler(request):
    call_command("update_repayment_status")  # <- your custom Django management command
    return {"statusCode": 200, "body": "Repayment status updated successfully"}