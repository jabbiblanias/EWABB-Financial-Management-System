from django.db import models, transaction
from django.contrib.auth.models import User
from accounts.models import Personalinfo


class Member(models.Model):
    member_id = models.AutoField(primary_key=True,db_column='memberid')
    user_id = models.ForeignKey(User, models.DO_NOTHING, db_column='userid')
    person_id = models.ForeignKey(Personalinfo, models.DO_NOTHING, db_column='personid')
    account_number = models.CharField(max_length=20, unique=True, blank=True, db_column='accountnumber')
    membership_date = models.DateField(auto_now_add=True, db_column='membershipdate')

    def save(self, *args, **kwargs):
        if not self.account_number:
            with transaction.atomic():
                # lock the table while checking last account
                last_account = (
                    Member.objects.select_for_update()
                    .order_by("-member_id")
                    .first()
                )
                next_id = 1 if not last_account else last_account.member_id + 1
                self.account_number = f"B-6-{str(next_id).zfill(2)}"
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.account_number} - {self.name}"

    class Meta:
        managed = False
        db_table = 'member'


class Savings(models.Model):
    savings_id = models.AutoField(primary_key=True, db_column='savingid')
    member_id = models.ForeignKey(Member, models.DO_NOTHING, db_column='memberid')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, db_column='balance')

    def __str__(self):
        return f"Savings #{self.id} - Member: {self.member}"
    
    class Meta:
        managed = False
        db_table = 'savings'