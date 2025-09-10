from celery import shared_task
from datetime import date
from .models import Appointments

@shared_task
def update_ended_appointments():
    now = date.today()
    updated = Appointments.objects.filter(
        appointment_date__lt=now,
        status__in=['Pending', 'Approved']  # not already ended/cancelled
    ).update(status='Ended')

    return f"Updated {updated} appointments to Ended"