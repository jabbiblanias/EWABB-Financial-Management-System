from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from .models import PersonalInfo, Spouse, MembershipApplication, Children
from datetime import date

def login_view(request):
    error = None
    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password')

        # Find user by username or email
        user_obj = User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()

        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            if user:
                login(request, user)
                return redirect('dashboard')

        error = "Invalid username/email or password"

    return render(request, 'accounts/login.html', {'error': error})

def logout_view(request):
    logout(request)
    return redirect('login')

def register_step1(request):
    if request.method == 'POST':
        surname = request.POST.get('surname')
        first_name = request.POST.get('firstName')
        name_extension = request.POST.get('nameExtension')
        middle_name = request.POST.get('middleName')
        date_of_birth = request.POST.get('dateOfBirth')
        place_of_birth = request.POST.get('placeOfBirth')
        gender = request.POST.get('gender')
        civil_status = request.POST.get('civilStatus')
        citizenship = request.POST.get('citizenship')
        height = request.POST.get('height')
        weight = request.POST.get('weight')
        blood_type = request.POST.get('bloodType')
        gsis_id_no = request.POST.get('gsisIdNo')
        pagibig_id_no = request.POST.get('pagibigIdNo')
        philhealth_id_no = request.POST.get('philhealthIdNo')
        sss_no = request.POST.get('sssNo')
        residential_address = request.POST.get('residentialAddress')
        residential_address_zip_code = request.POST.get('residentialAddressZipCode')
        residential_address_telephone_no = request.POST.get('residentialAddressTelephoneNo')
        permanent_address = request.POST.get('permanentAddress')
        permanent_address_zip_code = request.POST.get('permanentAddressZipCode')
        permanent_address_telephone_no = request.POST.get('permanentAddressTelephoneNo')
        contact_email_address = request.POST.get('contactEmailAddress')
        cellphone_no = request.POST.get('cellphoneNo')
        agency_employee_no = request.POST.get('agencyEmployeeNo')
        tin_no = request.POST.get('tinNo')

        # Save to session
        request.session['register_data'] = {
            'surname': surname,
            'firstName': first_name,
            'nameExtension': name_extension,
            'middleName': middle_name,
            'dateOfBirth': date_of_birth,
            'placeOfBirth': place_of_birth,
            'gender': gender,
            'civilStatus': civil_status,
            'citizenship': citizenship,
            'height': height,
            'weight': weight,
            'bloodType': blood_type,
            'gsisIdNo': gsis_id_no,
            'pagibigIdNo': pagibig_id_no,
            'philhealthIdNo': philhealth_id_no,
            'sssNo': sss_no,
            'residentialAddress': residential_address,
            'residentialAddressZipCode': residential_address_zip_code,
            'residentialAddressTelephoneNo': residential_address_telephone_no,
            'permanentAddress': permanent_address,
            'permanentAddressZipCode': permanent_address_zip_code,
            'permanentAddressTelephoneNo': permanent_address_telephone_no,
            'contactEmailAddress': contact_email_address,
            'cellphoneNo': cellphone_no,
            'agencyEmployeeNo': agency_employee_no,
            'tinNo': tin_no
        }
        return redirect('register_step2')

    return render(request, 'accounts/register_step1.html')

def register_step2(request):
    if request.method == 'POST':
        spouse_surname = request.POST.get('spouseSurname')
        spouse_first_name = request.POST.get('spouseFirstName')
        spouse_middle_name = request.POST.get('spouseMiddleName')
        occupation = request.POST.get('occupation')
        employer_bus_name = request.POST.get('employerBusinessName')
        business_address = request.POST.get('businessAddress')
        telephone_no = request.POST.get('businessTelephoneNo')

        children = request.POST.getlist('children')  # returns a list of all phone inputs

        emergency_contact_name = request.POST.get('emergencyContactName')
        emergency_contact_address = request.POST.get('emergencyContactAddress')

        # Update session data
        request.session['register_data'].update({
            'spouseSurname': spouse_surname,
            'spouseFirstName': spouse_first_name,
            'spouseMiddleName': spouse_middle_name,
            'occupation': occupation,
            'employerBusinessName': employer_bus_name,
            'businessAddress': business_address,
            'businessTelephoneNo': telephone_no,
            'children': children,
            'emergencyContactName': emergency_contact_name,
            'emergencyContactAddress': emergency_contact_address
        })
        return redirect('register_step3')

    return render(request, 'accounts/register_step2.html')

def register_step3(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Retrieve all session data
        data = request.session.get('register_data', {})

        surname = data.get('surname')
        first_name = data.get('firstName')
        name_extension = data.get('nameExtension')
        middle_name = data.get('middleName')
        date_of_birth = data.get('dateOfBirth')
        place_of_birth = data.get('placeOfBirth')
        gender = data.get('gender')
        civil_status = data.get('civilStatus')
        citizenship = data.get('citizenship')
        height = data.get('height')
        weight = data.get('weight')
        blood_type = data.get('bloodType')
        gsis_id_no = data.get('gsisIdNo')
        pagibig_id_no = data.get('pagibigIdNo')
        philhealth_id_no = data.get('philhealthIdNo')
        sss_no = request.POST.get('sssNo')
        residential_address = data.get('residentialAddress')
        residential_zip_code = data.get('residentialAddressZipCode')
        residential_telephone_no = data.get('residentialAddressTelephoneNo')
        permanent_address = data.get('permanentAddress')
        permanent_address_zip_code = data.get('permanentAddressZipCode')
        permanent_address_telephone_no = data.get('permanentAddressTelephoneNo')
        contact_email_address = data.get('contactEmailAddress')
        cellphone_no = data.get('cellphoneNo')
        agency_employee_no = data.get('agencyEmployeeNo')
        tin_no = data.get('tinNo')

        spouse_surname = data.get('spouseSurname')
        spouse_first_name = data.get('spouseFirstName')
        spouse_middle_name = data.get('spouseMiddleName')
        occupation = data.get('occupation')
        employer_bus_name = data.get('employerBusinessName')
        business_address = data.get('businessAddress')
        telephone_no = data.get('businessTelephoneNo')

        children = data.get('children', [])

        emergency_contact_name = data.get('emergencyContactName')
        emergency_contact_address = data.get('emergencyContactAddress')

        # Validate
        if password != confirm_password:
            error = "Passwords do not match."
        elif User.objects.filter(username=username).exists():
            error = "Username already taken."
        elif User.objects.filter(email=email).exists():
            error = "Email already registered."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            personal_info = PersonalInfo.objects.create(
                Surname=surname,
                FirstName=first_name,
                NameExtension=name_extension,
                MiddleName=middle_name,
                DateOfBirth=date_of_birth,
                PlaceOfBirth=place_of_birth,
                Gender=gender,
                CivilStatus=civil_status,
                Citizenship=citizenship,
                Height=height,
                Weight=weight,
                BloodType=blood_type,
                GSIS_ID_No=gsis_id_no,
                PAGIBIG_ID_No=pagibig_id_no,
                PHILHEALTH_ID_No=philhealth_id_no,
                SSS_No=sss_no,
                ResidentialAddress=residential_address,
                ResidentialaAddressZipCode=residential_zip_code,
                ResidentialAddressTelephoneNo=residential_telephone_no,
                PermanentAddress=permanent_address,
                PermamentAddressZipCode=permanent_address_zip_code,
                PermanentAddressTelephoneNo=permanent_address_telephone_no,
                ContactEmailAddress=contact_email_address,
                CellphoneNo=cellphone_no,
                AgencyEmployeeNo=agency_employee_no,
                TIN_No=tin_no
            )
            MembershipApplication.objects.create(
                user=user,
                personal_info=personal_info,
                DateAccomplished=date.today(),
                EmergencyContactName=emergency_contact_name,
                EmergencyContactAddress=emergency_contact_address
            )
            Spouse.objects.create(
                personal_info=personal_info,
                Surname=spouse_surname,
                FirstName=spouse_first_name,
                MiddleName=spouse_middle_name,
                Occupation=occupation,
                EmployerBusinessName=employer_bus_name,
                BusinessAddress=business_address,
                TelephoneNo=telephone_no
            )
            Children.objects.create(
                children=", ".join(children)
            )

            # Automatically assign user to 'Member' group
            member_group = Group.objects.get(name='Member')
            user.groups.add(member_group)

            # Clear session data
            request.session.pop('register_data', None)

            messages.success(request, "Account successfully created.")
            return redirect('login')

    return render(request, 'accounts/register_step3.html', {'error': error})
