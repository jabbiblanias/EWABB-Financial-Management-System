# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Personalinfo(models.Model):
    person_id = models.AutoField(primary_key=True,db_column='personid')
    surname = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50,db_column='firstname')
    name_extension = models.CharField(max_length=5, blank=True, null=True,db_column='nameextension')
    middle_name = models.CharField(max_length=50, blank=True, null=True,db_column='middlename')
    date_of_birth = models.DateField(blank=True, null=True,db_column='dateofbirth')
    place_of_birth = models.TextField(blank=True, null=True,db_column='placeofbirth')
    gender = models.CharField(max_length=10, blank=True, null=True)
    civil_status = models.CharField(max_length=20, blank=True, null=True,db_column='civilstatus')
    citizenship = models.CharField(max_length=50, blank=True, null=True)
    height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    blood_type = models.CharField(max_length=5, blank=True, null=True,db_column='bloodtype')
    gsis_id_no = models.CharField(max_length=30, blank=True, null=True)
    pagibig_id_no = models.CharField(max_length=30, blank=True, null=True, db_column='pagibig_no')
    philhealth_id_no = models.CharField(max_length=20, blank=True, null=True, db_column='philhealth_no')
    sss_id_no = models.CharField(max_length=20, blank=True, null=True, db_column='sss_no')
    residential_address = models.TextField(db_column='residentialaddress')
    residential_address_zip_code = models.CharField(max_length=10,db_column='residentialaddresszipcode')
    residential_address_telephone_no = models.CharField(max_length=15, blank=True, null=True,db_column='residentialaddresstelno')
    permanent_address = models.TextField(db_column='permanentaddress')
    permanent_address_zip_code = models.CharField(max_length=10, blank=True, null=True,db_column='permanentaddresszipcode')
    permanent_address_telephone_no = models.CharField(max_length=15, blank=True, null=True,db_column='permanentaddresstelno')
    contact_email_address = models.CharField(max_length=100, blank=True, null=True,db_column='contactemailaddress')
    cellphone_no = models.CharField(max_length=15, blank=True, null=True,db_column='cellphoneno')
    agency_employee_no = models.CharField(max_length=50,db_column='agencyemployeeno')
    tin_no = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'personalinfo'


class Membershipapplication(models.Model):
    application_id = models.AutoField(primary_key=True,db_column='applicationid')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='userid')
    person_id = models.ForeignKey(Personalinfo, models.DO_NOTHING, db_column='personid')
    date_accomplished = models.DateField(auto_now_add=True, db_column='dateaccomplished')
    emergency_contact_name = models.CharField(max_length=100, db_column='emergencycontactname')
    emergency_contact_address = models.TextField(db_column='emergencycontactaddress')
    status = models.CharField(max_length=10, default='Pending')
    verifier_id = models.ForeignKey(User, models.DO_NOTHING, db_column='verifierid', related_name='membershipapplication_verifierid_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'membershipapplication'


class Spouse(models.Model):
    spouse_id = models.AutoField(primary_key=True,db_column='spouseid')
    person_id = models.ForeignKey(Personalinfo, models.DO_NOTHING, db_column='personid', blank=True, null=True)
    spouse_first_name = models.CharField(max_length=50, blank=True, null=True,db_column='firstname')
    spouse_middle_name = models.CharField(max_length=50, blank=True, null=True,db_column='middlename')
    spouse_surname = models.CharField(max_length=50, blank=True, null=True, db_column='surname')
    occupation = models.CharField(max_length=100, blank=True, null=True)
    employer_business_name = models.CharField(max_length=100, blank=True, null=True,db_column='employerbusinessname')
    business_address = models.TextField(blank=True, null=True,db_column='businessaddress')
    telephone_no = models.CharField(max_length=20, blank=True, null=True,db_column='telephoneno')

    class Meta:
        managed = False
        db_table = 'spouse'


class Children(models.Model):
    child_id = models.AutoField(primary_key=True, db_column='childid')
    person_id = models.ForeignKey(Personalinfo, models.DO_NOTHING, db_column='personid', blank=True, null=True)
    full_name = models.CharField(max_length=100, blank=True, null=True,db_column='fullname')
    date_of_birth = models.DateField(blank=True, null=True,db_column='dateofbirth')

    class Meta:
        managed = False
        db_table = 'children'


class EmailOTP(models.Model):
    otp_id = models.AutoField(primary_key=True, db_column='otp_id')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='user_id', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    otp_code = models.CharField(max_length=6, db_column='otp_code')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_in = models.IntegerField(default=300)  # 5 minutes

    class Meta:
        managed = False
        db_table = 'otp'

    def is_valid(self):
        created = self.created_at
        if timezone.is_naive(created):
            created = timezone.make_aware(created, timezone.get_current_timezone())
        return (timezone.now() - created).total_seconds() < self.expires_in

