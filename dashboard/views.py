from django.shortcuts import render 
from django.contrib.auth.decorators import login_required
from members.models import Member
from members.models import Savings
from transactions.models import Transactions
from django.db.models import Sum, F, Case, When, DecimalField, Window
import json
from django.db.models.functions import TruncDate, TruncWeek, ExtractWeekDay, ExtractWeek, ExtractYear
from datetime import date, timedelta
from calendar import monthrange


@login_required
def dashboard_view(request):
    user = request.user
    
    if user.groups.filter(name='Admin').exists():
        return render(request, 'dashboard/admin.html')
    elif user.groups.filter(name='Member').exists():
        context = member_dashboard_data(user)
        return render(request, 'dashboard/member.html', context)
    elif user.groups.filter(name='Bookkeeper').exists():
        context = bookkeeper_dashboard_data()
        return render(request, 'dashboard/bookkeeper.html', context)
    elif user.groups.filter(name='Cashier').exists():
        return render(request, 'dashboard/cashier.html')
    

def member_dashboard_data(user):
    # 1️⃣ Get start (Sunday) and end (Saturday) of the current week
    today = date.today()
    start_of_week = today - timedelta(days=(today.weekday() + 1) % 7)  # previous Sunday
    end_of_week = start_of_week + timedelta(days=6)  # next Saturday

    # 2️⃣ Compute balance before this week (all transactions before Sunday)
    initial_balance_agg = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__lt=start_of_week,
        )
        .aggregate(
            balance=Sum(
                F("amount")
                * Case(
                    When(transaction_type="Withdrawal", then=-1),
                    default=1,
                    output_field=DecimalField(),
                )
            )
        )
    )
    initial_balance = initial_balance_agg['balance'] or 0

    # 3️⃣ Fetch transactions in current week, grouped by day
    weekly_qs = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__range=(start_of_week, end_of_week),
        )
        .annotate(date=TruncDate("transaction_date"))
        .annotate(
            signed_amount=F("amount")
            * Case(
                When(transaction_type="Withdrawal", then=-1),
                default=1,
                output_field=DecimalField(),
            )
        )
        .values("date")
        .annotate(daily_total=Sum("signed_amount"))  # 👈 sum per day
        .order_by("date")
    )

    # Put daily totals in a dict for easy lookup
    totals_dict = {row["date"]: row["daily_total"] for row in weekly_qs}

    # 4️⃣ Build Sun → Sat array for the current week (running balance)
    daily_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    daily_data = []
    running_balance = float(initial_balance)

    for i in range(7):
        day = start_of_week + timedelta(days=i)
        if day > today:  # ⛔ don't include future days
            break
        running_balance += float(totals_dict.get(day, 0) or 0)
        daily_data.append(running_balance)

        
    today = date.today()
    start_of_month = date(today.year, today.month, 1)
    end_of_month = date(today.year, today.month, monthrange(today.year, today.month)[1])

    # 2️⃣ Compute balance before this week (all transactions before Sunday)
    initial_balance_agg = (
        Transactions.objects.filter(
            member_id__user_id=user,
            transaction_type__in=["Savings Deposit", "Withdrawal"],
            transaction_date__date__lt=start_of_month,
        )
        .aggregate(
            balance=Sum(
                F("amount")
                * Case(
                    When(transaction_type="Withdrawal", then=-1),
                    default=1,
                    output_field=DecimalField(),
                )
            )
        )
    )
    initial_balance = initial_balance_agg['balance'] or 0

    # Query weekly totals for this month
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

    # Put into dict {(year, week): total}
    weekly_dict = {(row["year"], row["week"]): float(row["total"]) for row in weekly_qs}

    # Figure out which weeks belong to this month
    month_weeks = sorted(
        {d.isocalendar()[1] for d in (start_of_month + timedelta(days=i) for i in range((end_of_month - start_of_month).days + 1))}
    )
    current_year = today.year

    # Compute running balances
    running_balance = float(initial_balance)
    weekly_labels, weekly_data = [], []

    for week in month_weeks:
        key = (current_year, week)
        if key in weekly_dict:
            running_balance += weekly_dict[key]
            weekly_labels.append(f"Week {week}")
            weekly_data.append(running_balance)
        else:
            weekly_labels.append(f"Week {week}")
            weekly_data.append(None)  # 👈 leave weeks with no transactions empty

    # Query yearly totals
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

    # Put into dict {year: total}
    yearly_dict = {row["year"]: float(row["total"]) for row in yearly_qs}

    # Determine year range
    if yearly_dict:
        min_year = min(yearly_dict.keys())
        max_year = max(yearly_dict.keys())
    else:
        # no transactions → start from current year
        min_year = date.today().year
        max_year = min_year

    # Ensure up to 4 years, pad with future years if needed
    year_range = list(range(min_year, max_year + 1))[-4:]
    while len(year_range) < 4:
        year_range.append(year_range[-1] + 1)

    # Compute running balances
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

    balance = (
        Savings.objects
        .select_related("member_id__user_id")
        .get(member_id__user_id=user)
        .balance
    )

    # Return empty lists if there's no data
    if not daily_data:
        daily_labels = []
    if not weekly_data:
        weekly_labels = []
    if not yearly_data:
        yearly_labels = []
        
    context = {
        "daily_labels": json.dumps(daily_labels),
        "daily_data": json.dumps(daily_data),
        "weekly_labels": json.dumps(weekly_labels),
        "weekly_data": json.dumps(weekly_data),
        "yearly_labels": json.dumps(yearly_labels),
        "yearly_data": json.dumps(yearly_data),
        "balance":  balance
    }
    return context


def bookkeeper_dashboard_data():
    total_members = Member.objects.count()
    context = {"total_members": total_members}
    return context
    
