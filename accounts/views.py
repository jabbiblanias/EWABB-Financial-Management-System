from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from notifications.models import EmailOTP
from notifications.utils import otp
from django.db.models import Q, Value
from django.contrib.auth.models import User
from .models import Personalinfo, Spouse, Membershipapplication, Children, EmergencyContact
from members.models import Member
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.hashers import make_password, check_password
import json
from django.utils import timezone
from django.db.models.functions import Concat


def login_view(request):
    if request.method == 'POST':
        identifier = request.POST.get('emailUsername', '').strip()
        password = request.POST.get('password')

        # 🔍 Find user by email
        try:
            user_obj = User.objects.filter(Q(username=identifier) | Q(email=identifier)).first()
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user:
            email = user.email
            # ✅ Check membership status
            if Membershipapplication.objects.filter(user_id=user, status="Pending").exists(): 
                request.session["identifier"] = identifier
                messages.warning(request, "Your application is still pending.")
                return redirect("login")
            
            login(request, user)
            return redirect('dashboard')
            
            request.session["email"] = email
            request.session["user_id"] = user.id

            if user.groups.filter(name="Member").exists():
                member = Member.objects.select_related('person_id').get(user_id=user)
                first_name = member.person_id.first_name
            else:
                first_name = user.first_name
            otp(first_name, email)
            return redirect('login_verification')

        # ❌ Invalid login
        request.session["identifier"] = identifier
        messages.error(request, "Invalid email or password.")
        return redirect("login")

    return render(request, 'accounts/login.html')

def login_verification(request):
    if request.method == "POST":
        email = request.session["email"]
        user_id = request.session["user_id"]
        input_code = request.POST.get('code')
        otp = EmailOTP.objects.filter(email=email).latest('created_at')
        if not otp.is_valid():
            messages.error(request, "OTP expired")
            return redirect('register_verify')
        elif otp.otp_code != input_code:
            messages.error(request, "Invalid OTP")
        else:
            # ✅ Log in user
            user = User.objects.get(pk=user_id)
            login(request, user)
            return redirect('dashboard')

    return render(request, 'accounts/verification.html', {'form_action': 'login_verification'})

def home_page(request):
    return render(request, 'accounts/index.html')

def logout_view(request):
    logout(request)
    return redirect('login')

def profile_view(request):
    return render(request, 'accounts/profile.html')

def fetch_profile(request):
    user = request.user

    # MEMBER
    if user.groups.filter(name="Member").exists():
        profile = (
            Member.objects
            .select_related("person_id")
            .filter(user_id=user)
            .annotate(
                full_name=Concat(
                    'person_id__first_name',
                    Value(' '),
                    'person_id__surname'
                )
            )
            .values_list('full_name', flat=True)
            .first()
        )
        full_name = profile if profile else user.username

    # BOOKKEEPER, CASHIER, ADMIN
    elif (
        user.groups.filter(name="Bookkeeper").exists() or
        user.groups.filter(name="Cashier").exists() or
        user.groups.filter(name="Admin").exists()
    ):
        full_name = user.get_full_name() or user.username

    else:
        full_name = user.username

    first_letter = full_name[0].upper() if full_name else ""

    return JsonResponse({
        "full_name": full_name,
        "first_letter": first_letter
    })

def profile_information(request):
    user = request.user

    # MEMBER
    if user.groups.filter(name="Member").exists():
        member = Member.objects.select_related('person_id').get(user_id=user)
        # Handle spouse safely
        try:
            spouse = Spouse.objects.get(person_id=member.person_id)
        except Spouse.DoesNotExist:
            spouse = None

        # Handle children safely
        children = Children.objects.filter(person_id=member.person_id)  # returns queryset (empty if none)

        try:
            emergency_contact = EmergencyContact.objects.get(person_id=member.person_id)
        except EmergencyContact.DoesNotExist:
            emergency_contact = None

        context = {
            'member': member,
            'spouse': spouse,
            'children': children,
            'emergency_contact': emergency_contact
        }
    # BOOKKEEPER, CASHIER, ADMIN
    elif (
        user.groups.filter(name="Bookkeeper").exists() or
        user.groups.filter(name="Cashier").exists() or
        user.groups.filter(name="Admin").exists()
    ):
        full_name = user.get_full_name() or user.username

    else:
        full_name = user.username

    return render(request, 'accounts/profile.html', context)

from django.http import JsonResponse
from django.db.models import Q

def search_member(request):
    query = request.GET.get('q', '')
    results = []

    if query:
        members = Member.objects.select_related('person_id').filter(
            Q(person_id__first_name__icontains=query) |
            Q(person_id__surname__icontains=query) |
            Q(account_number__icontains=query)
        ).values(
            'member_id',
            'person_id__first_name',
            'person_id__surname',
            'account_number'
        )[:10]

        results = list(members)

    return JsonResponse(results, safe=False)


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
                'email': email,
                'password': make_password(password),
            })
            request.session['register_data'] = data
            request.session.modified = True  # ensures Django writes the session

            otp(first_name, email)
            
            return redirect('register_verify')

    return render(request, 'accounts/register3.html', {'error': error})


def registration_otp_verification_view(request):
    if request.method == "POST":
        data = request.session.get('register_data', {})
        input_code = request.POST.get('code')

        email = data.get('email')
        password = data.get('password')

        try:
            otp = EmailOTP.objects.filter(email=email).latest('created_at')

            if not otp.is_valid():
                messages.error(request, "OTP expired")
                return redirect('register_verify')
            elif otp.otp_code != input_code:
                messages.error(request, "Invalid OTP")
                return redirect('register_verify')
            else:
                try:
                    with transaction.atomic():

                        user = User.objects.create_user(
                            username="John",
                            email=email
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
                        
                        EmergencyContact.objects.create(
                            person_id=personid,
                            emergency_contact_name=data.get('emergencyContactName'),
                            emergency_contact_address=data.get('emergencyContactAddress')
                        )

                        Membershipapplication.objects.create(
                            user_id=user,
                            person_id=personid
                        )

                        # All succeeded, clear session
                        request.session.pop('register_data', None)
                        return redirect('complete_registration')

                except IntegrityError as e:
                    # Everything rolled back, but we know where it failed
                    messages.error(request, "Registration failed. Please try again.")
                    return redirect('register3')

        except EmailOTP.DoesNotExist:
            messages.error(request, "OTP not found")
            return redirect('register_verify')

    return render(request, 'accounts/verification.html', {'form_action': 'register_verify'})


def check_email(request):
    email = request.GET.get("email")
    exists = User.objects.filter(email=email).exists()
    return JsonResponse({"exists": exists})


def update_timer(request):
    email = None
    if "register_data" in request.session:
        email = request.session.get("register_data", {}).get("email")
    elif "email" in request.session:
        email = request.session.get("email")
    if not email:
        return JsonResponse({"status": False, "message": "No email in session"})

    try:
        otp = EmailOTP.objects.filter(email=email).latest('created_at')
    except EmailOTP.DoesNotExist:
        return JsonResponse({"status": False, "message": "No OTP found"})

    created = otp.created_at
    if timezone.is_naive(created):
        created = timezone.make_aware(created, timezone.get_current_timezone())

    cooldown_seconds = 60
    elapsed = (timezone.now() - created).total_seconds()
    remaining = max(0, cooldown_seconds - elapsed)

    # status True = still counting down / cannot resend yet
    return JsonResponse({
        "status": remaining > 0,
        "remaining": remaining
    })
    

def resend_otp(request):
    # Check both registration and login sessions
    email = None
    first_name = None
    if "register_data" in request.session:
        data = request.session["register_data"]
        email = data.get("email")
        first_name = data.get("first_name")
    elif "email" and "first_name" in request.session:
        email = request.session["email"]
        first_name = request.session["first_name"]

    if not email:
        return JsonResponse({"status": False, "message": "No email in session"})

    # Call your function to generate and send OTP
    otp(first_name, email)

    return JsonResponse({"status": True, "message": "OTP resent successfully"})

def success_view(request):
    return render(request, 'accounts/success.html')