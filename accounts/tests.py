from django.test import TestCase
from django.contrib.auth.models import User, Group
from .models import Personalinfo, Spouse, Membershipapplication
from datetime import date

class MembershipTestCase(TestCase):
    def setUp(self):
        person = Personalinfo.objects.create(
            surname="Doe",
            first_name="John",
            middle_name="Smith",
            name_extension="Jr",
            date_of_birth="1990-01-01",
            place_of_birth="Quezon City",
            gender="Male",
            civil_status="Single",
            citizenship="Filipino",
            height=170.25,
            weight=65.50,
            blood_type="O+",
            gsis_id_no="123456789",
            pagibig_id_no="987654321",
            philhealth_id_no="11223344",
            sss_id_no="55667788",
            residential_address="123 Elm Street",
            residential_address_zip_code="1100",
            residential_address_telephone_no="02-1234567",
            permanent_address="123 Elm Street",
            permanent_address_zip_code="1100",
            permanent_address_telephone_no="02-1234567",
            contact_email_address="john.doe@email.com",
            cellphone_no="09171234567",
            agency_employee_no="EMP001",
            tin_no="123456789"
        )

        user = User.objects.create_user(username='johndoe', email='jabbiblanias@gmail.com', password="mypassword123")

        application = Membershipapplication.objects.create(
            user_id=user,
            person_id=person,
            date_accomplished=date.today(),
            emergency_contact_name="Jane Doe",
            emergency_contact_address="456 Maple Avenue"
        )

        spouse = Spouse.objects.create(
            person_id=person,
            spouse_first_name="Jane",
            spouse_middle_name="Marie",
            spouse_surname="Doe",
            occupation="Engineer",
            employer_business_name="TechCorp",
            business_address="789 Tech Park",
            telephone_no="027654321"
        )

        member_group = Group.objects.get(name='Member')
        user.groups.add(member_group)

    def test_membership_creation(self):
        self.assertTrue(User.objects.filter(username='johndoe').exists())
