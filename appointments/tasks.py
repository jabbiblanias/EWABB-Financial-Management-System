from celery import shared_task
from django.utils import timezone
from .models import Appointments

import logging
logger = logging.getLogger(__name__)

@shared_task
def update_ended_appointments():
    now = timezone.localtime(timezone.now())
    updated = Appointments.objects.filter(
        appointment_date__lt=now,
        status__in=['Pending', 'Approved']
    ).update(status='Ended')

    logger.info(f"Updated {updated} appointments to Ended")
    return updated  # return an integer (safe for Celery)