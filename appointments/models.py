from django.db import models
from django.contrib.auth.models import User
from members.models import Member


class Appointments(models.Model):
    APPOINTMENT_TYPES = [
        ('Consultation', 'Consultation'),
        ('Follow-up', 'Follow-up'),
        ('Inquiry', 'Inquiry'),
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Cancelled', 'Cancelled'),
    ]

    appointment_id = models.AutoField(primary_key=True, db_column='appointmentid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    appointment_date = models.DateField(db_column='date')
    appointment_time = models.TimeField(db_column='time')
    appointment_type = models.CharField(max_length=15, choices=APPOINTMENT_TYPES, db_column='appointmenttype')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending', db_column='status')
    bookkeeper_id = models.ForeignKey(User, models.DO_NOTHING, related_name='bookkeeper_appointments', db_column='id')

    def __str__(self):
        return f"{self.appointment_type} with {self.member} on {self.date}"
