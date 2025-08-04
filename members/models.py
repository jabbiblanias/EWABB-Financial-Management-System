from django.db import models
from django.contrib.auth.models import User
from accounts.models import Personalinfo


class Member(models.Model):
    member_id = models.AutoField(primary_key=True,db_column='memberid')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='userid')
    person_id = models.ForeignKey(Personalinfo, models.DO_NOTHING, db_column='personid')
    account_number = models.CharField(max_length=50,db_column='accountnumber')
    membership_date = models.DateField(auto_now_add=True, db_column='membershipdate')

    class Meta:
        managed = False
        db_table = 'member'