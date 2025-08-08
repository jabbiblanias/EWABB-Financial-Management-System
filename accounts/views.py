from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.template import Context
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from .models import Personalinfo, Spouse, Membershipapplication, Children
from datetime import date

def login_view(request):
    error = None
    if request.method == 'POST':
        identifier = request.POST.get('emailUsername', '').strip()
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

def home_page(request):
    return render(request, 'accounts/index.html')

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
        sss_id_no = request.POST.get('sssNo')
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
            'sssNo': sss_id_no,
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
        return redirect('register2')

    return render(request, 'accounts/register1.html')

def register_step2(request):
    if request.method == 'POST':
        spouse_surname = request.POST.get('spouseSurname')
        spouse_first_name = request.POST.get('spouseFirstName')
        spouse_middle_name = request.POST.get('spouseMiddleName')
        occupation = request.POST.get('occupation')
        employer_bus_name = request.POST.get('employerBusinessName')
        business_address = request.POST.get('businessAddress')
        telephone_no = request.POST.get('businessTelephoneNo')

        child_full_name = request.POST.getlist('childName')
        child_date_of_birth = request.POST.getlist('childDateOfBirth')
        children = list(zip(child_full_name, child_date_of_birth))

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
        return redirect('register3')

    return render(request, 'accounts/register2.html')

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
        sss_id_no = data.get('sssNo')
        residential_address = data.get('residentialAddress')
        residential_address_zip_code = data.get('residentialAddressZipCode')
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

            # Automatically assign user to 'Member' group
            member_group = Group.objects.get(name='Member')
            user.groups.add(member_group)

            personid = Personalinfo.objects.create(
                surname=surname,
                first_name=first_name,
                name_extension=name_extension,
                middle_name=middle_name,
                date_of_birth=date_of_birth,
                place_of_birth=place_of_birth,
                gender=gender,
                civil_status=civil_status,
                citizenship=citizenship,
                height=height,
                weight=weight,
                blood_type=blood_type,
                gsis_id_no=gsis_id_no,
                pagibig_id_no=pagibig_id_no,
                philhealth_id_no=philhealth_id_no,
                sss_id_no=sss_id_no,
                residential_address=residential_address,
                residential_address_zip_code=residential_address_zip_code,
                residential_address_telephone_no=residential_telephone_no,
                permanent_address=permanent_address,
                permanent_address_zip_code=permanent_address_zip_code,
                permanent_address_telephone_no=permanent_address_telephone_no,
                contact_email_address=contact_email_address,
                cellphone_no=cellphone_no,
                agency_employee_no=agency_employee_no,
                tin_no=tin_no
            )
            
            Spouse.objects.create(
                person_id=personid,
                spouse_surname=spouse_surname,
                spouse_first_name=spouse_first_name,
                spouse_middle_name=spouse_middle_name,
                occupation=occupation,
                employer_business_name=employer_bus_name,
                business_address=business_address,
                telephone_no=telephone_no
            )

            for name, bday in children:
                Children.objects.create(
                    person_id=personid, 
                    child_full_name=name, 
                    child_date_of_birth=bday
                )

            Membershipapplication.objects.create(
                user_id=user,
                person_id=personid,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_address=emergency_contact_address
            )

            # Clear session data
            request.session.pop('register_data', None)

            messages.success(request, "Account successfully created.")
            return redirect('login')

    return render(request, 'accounts/register3.html', {'error': error})
