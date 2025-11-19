from django.shortcuts import render 
from django.contrib.auth.decorators import login_required
from members.models import Member, Savings
from loans.models import LoanApplication, LoanRepaymentSchedule
from transactions.models import Transactions
from django.db.models import Sum, F, Case, When, DecimalField, Window
import json
from django.db.models.functions import TruncDate, TruncWeek, ExtractWeekDay, ExtractWeek, ExtractYear
from datetime import date, timedelta
from calendar import monthrange
from django.utils import timezone
from django.db.models import Sum, F, Case, When, DecimalField
from django.db.models.functions import TruncDate, ExtractWeek, ExtractYear, ExtractMonth
import calendar
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.utils.timezone import now
from loans.models import Loan
from .models import CashierStatus
from django.http import JsonResponse
from financial_reporting.models import Funds, Revenue

@login_required
def dashboard_view(request):
    user = request.user
    
    if user.groups.filter(name='Admin').exists():
        context = admin_dashboard_data()
        return render(request, 'dashboard/admin.html', context)
    elif user.groups.filter(name='Member').exists():
        context = member_dashboard_data(user)
        return render(request, 'dashboard/member.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        context = bookkeeper_dashboard_data()
        return render(request, 'dashboard/bookkeeper.html', context)
    elif user.groups.filter(name='Cashier').exists():
        context = cashier_dashboard_data(request)
        return render(request, 'dashboard/cashier.html', context)
    

def member_dashboard_data(user):
    today = date.today()

    # ---------- 🟢 DAILY ----------
    start_of_week = today - timedelta(days=(today.weekday() + 1) % 7)
    end_of_week = start_of_week + timedelta(days=6)

    initial_balance_agg = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__lt=start_of_week,
        )
        .aggregate(
            balance=Sum(
                F("amount") *
                Case(
                    When(transaction_type="Withdrawal", then=-1),
                    default=1,
                    output_field=DecimalField(),
                )
            )
        )
    )
    initial_balance = initial_balance_agg['balance'] or 0

    daily_qs = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__range=(start_of_week, end_of_week),
        )
        .annotate(date=TruncDate("transaction_date"))
        .annotate(
            signed_amount=F("amount") *
            Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField(),
            )
        )
        .values("date")
        .annotate(daily_total=Sum("signed_amount"))
        .order_by("date")
    )

    totals_dict = {row["date"]: row["daily_total"] for row in daily_qs}

    daily_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    daily_data = []
    running_balance = float(initial_balance)

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        if day > today:
            break
        running_balance += float(totals_dict.get(day, 0) or 0)
        daily_data.append(running_balance)

    # ---------- 🟡 WEEKLY ----------
    start_of_month = date(today.year, today.month, 1)
    end_of_month = date(today.year, today.month, monthrange(today.year, today.month)[1])

    initial_balance_agg = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__lt=start_of_month,
        )
        .aggregate(
            balance=Sum(
                F("amount") *
                Case(
                    When(transaction_type="Withdrawal", then=-1),
                    default=1,
                    output_field=DecimalField(),
                )
            )
        )
    )
    initial_balance = initial_balance_agg['balance'] or 0

    weekly_qs = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__range=(start_of_month, end_of_month),
        )
        .annotate(
            week=ExtractWeek("transaction_date"),
            year=ExtractYear("transaction_date"),
            signed_amount=F("amount") * Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField(),
            ),
        )
        .values("year", "week")
        .annotate(total=Sum("signed_amount"))
        .order_by("year", "week")
    )

    weekly_dict = {(row["year"], row["week"]): float(row["total"]) for row in weekly_qs}
    month_weeks = sorted({
        d.isocalendar()[1]
        for d in (start_of_month + timedelta(days=i) for i in range((end_of_month - start_of_month).days + 1))
    })
    current_year = today.year

    running_balance = float(initial_balance)
    weekly_labels, weekly_data = [], []

    for week in month_weeks:
        key = (current_year, week)
        running_balance += weekly_dict.get(key, 0)
        weekly_labels.append(f"Week {week}")
        weekly_data.append(running_balance if key in weekly_dict else None)

    # ---------- 🔵 MONTHLY (NEW SECTION) ----------
    monthly_qs = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__year=today.year,
        )
        .annotate(
            month=ExtractMonth("transaction_date"),
            signed_amount=F("amount") *
            Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField(),
            )
        )
        .values("month")
        .annotate(total=Sum("signed_amount"))
        .order_by("month")
    )

    monthly_dict = {row["month"]: float(row["total"]) for row in monthly_qs}
    running_balance = 0
    monthly_labels, monthly_data = [], []

    for month in range(1, 13):
        running_balance += monthly_dict.get(month, 0)
        monthly_labels.append(date(today.year, month, 1).strftime("%b"))  # e.g., Jan, Feb
        monthly_data.append(running_balance if month in monthly_dict else None)

    # ---------- 🔴 YEARLY ----------
    yearly_qs = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"]
        )
        .annotate(
            year=ExtractYear("transaction_date"),
            signed_amount=F("amount") * Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField()
            )
        )
        .values("year")
        .annotate(total=Sum("signed_amount"))
        .order_by("year")
    )

    yearly_dict = {row["year"]: float(row["total"]) for row in yearly_qs}

    if yearly_dict:
        min_year = min(yearly_dict.keys())
        max_year = max(yearly_dict.keys())
    else:
        min_year = today.year
        max_year = min_year

    year_range = list(range(min_year, max_year + 1))[-4:]
    while len(year_range) < 4:
        year_range.append(year_range[-1] + 1)

    running_balance = 0
    yearly_labels, yearly_data = [], []

    for y in year_range:
        running_balance += yearly_dict.get(y, 0)
        yearly_labels.append(str(y))
        yearly_data.append(running_balance if y in yearly_dict else None)

    # ---------- BALANCE ----------
    balance = (
        Savings.objects
        .select_related("member_id__user_id")
        .get(member_id__user_id=user)
        .balance
    )

    loan_exists = Loan.objects.filter(member_id__user_id=user, loan_status="Active").exists()
    loan_balance = 0
    next_due = None
    due_amount = None

    if loan_exists:
        active_loan = Loan.objects.get(member_id__user_id=user, loan_status="Active")
        loan_balance += active_loan.remaining_balance

        next_due = LoanRepaymentSchedule.objects.filter(
            loan_id=active_loan
        ).order_by("due_date").exists()

        if next_due:
            next_due = LoanRepaymentSchedule.objects.filter(
                loan_id=active_loan
            ).order_by("due_date").first().due_date
            due_amount = LoanRepaymentSchedule.objects.filter(
                loan_id=active_loan
            ).order_by("due_date").first().amount_due



    # ---------- CONTEXT ----------
    context = {
        "daily_labels": json.dumps(daily_labels),
        "daily_data": json.dumps(daily_data),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_data": json.dumps(monthly_data),
        "yearly_labels": json.dumps(yearly_labels),
        "yearly_data": json.dumps(yearly_data),
        "balance": balance,
        "loan_balance": loan_balance,
        "next_due": next_due,
        "due_amount": due_amount
    }
    return context



def bookkeeper_dashboard_data():
    total_members = Member.objects.count()
    pending_verification = LoanApplication.objects.filter(status="Pending").count()
    total_loans = Loan.objects.aggregate(total=Sum('remaining_balance'))['total'] or 0
    total_savings = Savings.objects.aggregate(total=Sum('balance'))['total'] or 0

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday() + 1)  # Sunday
    end_of_week = start_of_week + timedelta(days=6)  # Saturday

    # --- DAILY (Sunday → Saturday cumulative including past members)
    daily_labels = []
    daily_counts = []

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        daily_labels.append(day.strftime('%a'))  # Sun, Mon, Tue...
        total_members = Member.objects.filter(membership_date__lte=day).count()
        daily_counts.append(total_members)

    # --- MONTHLY (Jan–Dec cumulative)
    monthly_data = (
        Member.objects.annotate(month=TruncMonth('membership_date'))
        .values('month')
        .annotate(count=Count('member_id'))
        .order_by('month')
    )

    monthly_labels = [calendar.month_abbr[m] for m in range(1, 13)]
    monthly_counts = []
    cumulative = 0

    for month_index in range(1, 13):
        new_members = next(
            (item['count'] for item in monthly_data if item['month'].month == month_index),
            0
        )
        cumulative += new_members
        monthly_counts.append(cumulative)

    # --- YEARLY (latest 5 years cumulative)
    yearly_data = (
        Member.objects.annotate(year=TruncYear('membership_date'))
        .values('year')
        .annotate(count=Count('member_id'))
        .order_by('year')
    )

    yearly_labels = [str(item['year'].year) for item in yearly_data]
    yearly_counts = []
    cumulative = 0

    for item in yearly_data:
        cumulative += item['count']
        yearly_counts.append(cumulative)

    context = {
        'daily_labels': json.dumps(daily_labels),
        'daily_data': json.dumps(daily_counts),
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_data': json.dumps(monthly_counts),
        'yearly_labels': json.dumps(yearly_labels),
        'yearly_data': json.dumps(yearly_counts),
        "total_members": total_members,
        "total_loan": total_loans,
        "total_savings": total_savings,
        "verification": pending_verification
    }
    return context

def cashier_dashboard_data(request):
    cashier = request.user  # Logged-in cashier
    today = timezone.localdate()

    loans = LoanApplication.objects.filter(status='Approved').count()
    total_collection = Transactions.objects.filter(
        cashier_id=cashier,
        transaction_type__in=['Savings Deposit', 'Loan Payment', 'Program Deposit'],
        transaction_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_payouts = Transactions.objects.filter(
        cashier_id=cashier,
        transaction_type__in=['Withdrawal', 'Loan Release', 'Operating Expenses'],
        transaction_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    cashier_availability = cashier.cashierstatus.status if hasattr(cashier, 'cashierstatus') else 'unavailable'

    # === Get current week range (Sunday → Saturday) ===
    today = timezone.localtime().date()
    start_of_week = today - timedelta(days=today.weekday() + 1) if today.weekday() != 6 else today
    # (weekday(): 0=Mon, 6=Sun)
    # Adjust to previous Sunday if today isn’t Sunday
    start_of_week = start_of_week if start_of_week.weekday() == 6 else start_of_week - timedelta(days=start_of_week.weekday() + 1)
    end_of_week = start_of_week + timedelta(days=6)

    # === DAILY TRANSACTIONS (Sunday–Saturday) ===
    daily_qs = (
        Transactions.objects.filter(
            cashier_id=cashier,
            transaction_date__date__gte=start_of_week,
            transaction_date__date__lte=end_of_week,
        )
        .annotate(day=TruncDay('transaction_date'))
        .values('day')
        .annotate(total_amount=Sum('amount'))
        .order_by('day')
    )

    # Create dictionary for quick lookup
    daily_map = {item['day'].date(): float(item['total_amount']) for item in daily_qs}

    # Generate ordered week labels (Sun–Sat)
    week_labels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    daily_labels = []
    daily_data = []

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        daily_labels.append(week_labels[i])
        daily_data.append(daily_map.get(day, 0.0))  # Fill missing days with 0

    # === MONTHLY TRANSACTIONS (Jan–Dec, this year) ===
    current_year = today.year
    monthly_qs = (
        Transactions.objects.filter(
            cashier_id=cashier,
            transaction_date__year=current_year
        )
        .annotate(month=TruncMonth('transaction_date'))
        .values('month')
        .annotate(total_amount=Sum('amount'))
        .order_by('month')
    )

    # Initialize 12 months with zero
    monthly_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_data = [0.0] * 12

    for item in monthly_qs:
        month_index = item['month'].month - 1
        monthly_data[month_index] = float(item['total_amount'])

     # === YEARLY TRANSACTIONS (Running balance per year, up to 4 years) ===
    yearly_qs = (
        Transactions.objects.filter(cashier_id=cashier)
        .annotate(
            year=ExtractYear("transaction_date"),
            signed_amount=F("amount") * Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField(),
            ),
        )
        .values("year")
        .annotate(total=Sum("signed_amount"))
        .order_by("year")
    )

    yearly_dict = {row["year"]: float(row["total"]) for row in yearly_qs}

    if yearly_dict:
        min_year = min(yearly_dict.keys())
        max_year = max(yearly_dict.keys())
    else:
        min_year = date.today().year
        max_year = min_year

    year_range = list(range(min_year, max_year + 1))[-4:]
    while len(year_range) < 4:
        year_range.append(year_range[-1] + 1)

    running_balance = 0
    yearly_labels, yearly_data = [], []

    for y in year_range:
        if y in yearly_dict:
            running_balance += yearly_dict[y]
            yearly_labels.append(str(y))
            yearly_data.append(running_balance)
        else:
            yearly_labels.append(str(y))
            yearly_data.append(None)
    context = {
        "daily_labels": json.dumps(daily_labels),
        "daily_data": json.dumps(daily_data),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_data": json.dumps(monthly_data),
        "yearly_labels": json.dumps(yearly_labels),
        "yearly_data": json.dumps(yearly_data),
        "loans": loans,
        "total_collection": total_collection,
        "total_payouts": total_payouts,
        "cashier_availability": cashier_availability,
    }
    return context

def admin_dashboard_data():
    current_year = timezone.localdate().year
    revenue = Funds.objects.filter(fund_name="Revenue").first()
    expenses = Funds.objects.filter(fund_name="Expenses").first()
    total_members = Member.objects.count()
    pending_approval = LoanApplication.objects.filter(status="Verified").count()
    total_loans = Loan.objects.aggregate(total=Sum('remaining_balance'))['total'] or 0
    total_savings = Savings.objects.aggregate(total=Sum('balance'))['total'] or 0

    today = date.today()

    # ---------- 🟢 DAILY ----------
    start_of_week = today - timedelta(days=(today.weekday() + 1) % 7)
    end_of_week = start_of_week + timedelta(days=6)

    # Total before the current week (initial)
    initial_revenue_agg = (
        Revenue.objects.filter(date_collected__date__lt=start_of_week)
        .aggregate(total=Sum("amount"))
    )
    initial_revenue = initial_revenue_agg["total"] or 0

    # Revenue per day for this week
    daily_qs = (
        Revenue.objects.filter(date_collected__date__range=(start_of_week, end_of_week))
        .annotate(date=TruncDate("date_collected"))
        .values("date")
        .annotate(daily_total=Sum("amount"))
        .order_by("date")
    )

    totals_dict = {row["date"]: float(row["daily_total"]) for row in daily_qs}
    daily_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

    daily_data = []
    running_total = float(initial_revenue)

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        if day > today:
            break
        running_total += float(totals_dict.get(day, 0) or 0)
        daily_data.append(running_total)

    # ---------- 🟡 WEEKLY ----------
    start_of_month = date(today.year, today.month, 1)
    end_of_month = date(today.year, today.month, monthrange(today.year, today.month)[1])

    initial_revenue_agg = (
        Revenue.objects.filter(date_collected__date__lt=start_of_month)
        .aggregate(total=Sum("amount"))
    )
    initial_revenue = initial_revenue_agg["total"] or 0

    weekly_qs = (
        Revenue.objects.filter(date_collected__date__range=(start_of_month, end_of_month))
        .annotate(
            week=ExtractWeek("date_collected"),
            year=ExtractYear("date_collected")
        )
        .values("year", "week")
        .annotate(total=Sum("amount"))
        .order_by("year", "week")
    )

    weekly_dict = {(row["year"], row["week"]): float(row["total"]) for row in weekly_qs}
    month_weeks = sorted({
        d.isocalendar()[1]
        for d in (start_of_month + timedelta(days=i)
                  for i in range((end_of_month - start_of_month).days + 1))
    })
    current_year = today.year

    running_total = float(initial_revenue)
    weekly_labels, weekly_data = [], []

    for week in month_weeks:
        key = (current_year, week)
        running_total += weekly_dict.get(key, 0)
        weekly_labels.append(f"Week {week}")
        weekly_data.append(running_total if key in weekly_dict else None)

    # ---------- 🔵 MONTHLY ----------
    monthly_qs = (
        Revenue.objects.filter(date_collected__year=today.year)
        .annotate(month=ExtractMonth("date_collected"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )

    monthly_dict = {row["month"]: float(row["total"]) for row in monthly_qs}
    running_total = 0
    monthly_labels, monthly_data = [], []

    for month in range(1, 13):
        running_total += monthly_dict.get(month, 0)
        monthly_labels.append(date(today.year, month, 1).strftime("%b"))
        monthly_data.append(running_total if month in monthly_dict else None)

    # ---------- 🔴 YEARLY ----------
    yearly_qs = (
        Revenue.objects.all()
        .annotate(year=ExtractYear("date_collected"))
        .values("year")
        .annotate(total=Sum("amount"))
        .order_by("year")
    )

    yearly_dict = {row["year"]: float(row["total"]) for row in yearly_qs}

    if yearly_dict:
        min_year = min(yearly_dict.keys())
        max_year = max(yearly_dict.keys())
    else:
        min_year = today.year
        max_year = min_year

    year_range = list(range(min_year, max_year + 1))[-4:]
    while len(year_range) < 4:
        year_range.append(year_range[-1] + 1)

    running_total = 0
    yearly_labels, yearly_data = [], []

    for y in year_range:
        running_total += yearly_dict.get(y, 0)
        yearly_labels.append(str(y))
        yearly_data.append(running_total if y in yearly_dict else None)

    # ---------- CONTEXT ----------
    context = {
        "available_operating_expenses": expenses.balance if expenses else 0,
        "total_loan": total_loans,
        "revenue": revenue.balance if revenue else 0,
        "approvals": pending_approval,
        "current_year": current_year,
        "daily_labels": json.dumps(daily_labels),
        "daily_data": json.dumps(daily_data),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_data": json.dumps(weekly_data),
        "monthly_labels": json.dumps(monthly_labels),
        "monthly_data": json.dumps(monthly_data),
        "yearly_labels": json.dumps(yearly_labels),
        "yearly_data": json.dumps(yearly_data),
    }
    print(context)
    return context


def cashier_status(request):
    user = request.user
    cashier = CashierStatus.objects.get(user_id=user)
    cashier_availability = cashier.status
    return JsonResponse({"status": cashier_availability})

def update_status(request):
    if request.method == "POST":
        data = json.loads(request.body)
        status = data.get("status")
        user = request.user

        CashierStatus.objects.filter(user_id=user).update(status=status)
        cashier = CashierStatus.objects.get(user_id=user)
        cashier_availability = cashier.status
        return JsonResponse({"status": cashier_availability})

def cashier_transaction_availablity(request):
    user = request.user
    cashier_availability = CashierStatus.objects.filter(status="available").exists()
    return JsonResponse({"status": cashier_availability})