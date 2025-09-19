from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from notifications.models import EmailOTP
from notifications.utils import registration_otp
from django.db.models import Q
from django.contrib.auth.models import User
from .models import Personalinfo, Spouse, Membershipapplication, Children
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password


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
                if Membershipapplication.objects.filter(user_id=user, status="Pending").exists():
                    error = "Application is still pending"
                    return render(request, "accounts/login.html", {
                        "pending_message": error,
                        "emailUsername": identifier
                    })
                login(request, user)
                return redirect('dashboard')

        error = "Invalid username/email or password"

    return render(request, 'accounts/login.html', {'error_message': error})

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
        print("In register2:", request.session.get('register_data'))
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
        
        data = request.session.get('register_data', {})

        data.update({
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

        request.session['register_data'] = data
        request.session.modified = True  # ensures Django writes the session
        return redirect('register3')

    return render(request, 'accounts/register2.html')


def register_step3(request):
    error = None
    print("In register3:", request.session.get('register_data'))
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validate
        if password != confirm_password:
            error = "Passwords do not match."
        elif User.objects.filter(username=username).exists():
            error = "Username already taken."
        elif User.objects.filter(email=email).exists():
            error = "Email already registered."
        else:
            # Retrieve all session data
            data = request.session.get('register_data', {})

            first_name = data.get('firstName')

            data.update({
                'username': username,
                'email': email,
                'password': make_password(password),
            })
            request.session['register_data'] = data
            request.session.modified = True  # ensures Django writes the session

            if registration_otp(first_name, email):
                return redirect('register_verify')
            else:
                error = "Invalid or unreachable email address. Please try again."

    return render(request, 'accounts/register3.html', {'error': error})


def registration_otp_verification_view(request):
    error = None
    print("In verification:", request.session.get('register_data'))

    if request.method == "POST":
        data = request.session.get('register_data', {})
        input_code = request.POST.get('code')

        email = data.get('email')
        username = data.get('username')
        password = data.get('password')

        try:
            otp = EmailOTP.objects.filter(email=email).latest('created_at')

            if not otp.is_valid():
                error = "OTP expired"
            elif otp.otp_code != input_code:
                error = "Invalid OTP"
            else:
                try:
                    with transaction.atomic():

                        user = User.objects.create_user(
                            username=username,
                            email=email,
                        )
                        user.password = password  # assign directly, already hashed
                        user.save()

                        personid = Personalinfo.objects.create(
                            surname=data.get('surname'),
                            first_name=data.get('firstName'),
                            name_extension=data.get('nameExtension'),
                            middle_name=data.get('middleName'),
                            date_of_birth=data.get('dateOfBirth'),
                            place_of_birth=data.get('placeOfBirth'),
                            gender=data.get('gender'),
                            civil_status=data.get('civilStatus'),
                            citizenship=data.get('citizenship'),
                            height=data.get('height'),
                            weight=data.get('weight'),
                            blood_type=data.get('bloodType'),
                            gsis_id_no=data.get('gsisIdNo'),
                            pagibig_id_no=data.get('pagibigIdNo'),
                            philhealth_id_no=data.get('philhealthIdNo'),
                            sss_id_no=data.get('sssNo'),
                            residential_address=data.get('residentialAddress'),
                            residential_address_zip_code=data.get('residentialAddressZipCode'),
                            residential_address_telephone_no=data.get('residentialAddressTelephoneNo'),
                            permanent_address=data.get('permanentAddress'),
                            permanent_address_zip_code=data.get('permanentAddressZipCode'),
                            permanent_address_telephone_no=data.get('permanentAddressTelephoneNo'),
                            contact_email_address=data.get('contactEmailAddress'),
                            cellphone_no=data.get('cellphoneNo'),
                            agency_employee_no=data.get('agencyEmployeeNo'),
                            tin_no=data.get('tinNo')
                        )

                        if data.get('spouseSurname') and data.get('spouseFirstName'):
                            Spouse.objects.create(
                                person_id=personid,
                                spouse_surname=data.get('spouseSurname'),
                                spouse_first_name=data.get('spouseFirstName'),
                                spouse_middle_name=data.get('spouseMiddleName'),
                                occupation=data.get('occupation'),
                                employer_business_name=data.get('employerBusinessName'),
                                business_address=data.get('businessAddress'),
                                telephone_no=data.get('businessTelephoneNo')
                            )

                        for name, bday in data.get('children', []):
                            if name and bday:
                                Children.objects.create(
                                    person_id=personid,
                                    full_name=name,
                                    date_of_birth=bday
                                )

                        Membershipapplication.objects.create(
                            user_id=user,
                            person_id=personid,
                            emergency_contact_name=data.get('emergencyContactName'),
                            emergency_contact_address=data.get('emergencyContactAddress')
                        )

                        # All succeeded, clear session
                        request.session.pop('register_data', None)
                        return redirect('complete_registration')

                except IntegrityError as e:
                    # Everything rolled back, but we know where it failed
                    messages.error(request, "Registration failed. Please try again.")
                    return redirect('register3')

        except EmailOTP.DoesNotExist:
            error = "OTP not found"

    return render(request, 'accounts/verification.html', {'error': error})


def check_email(request):
    email = request.GET.get("email")
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({"exists": exists})


def check_username(request):
    username = request.GET.get("username")
    exists = User.objects.filter(username=username).exists()
    return JsonResponse({"exists": exists})


def success_view(request):
    return render(request, 'accounts/success.html')