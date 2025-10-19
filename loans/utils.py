from decimal import Decimal
import re

def extract_months(term: str) -> int:
    """Helper function to parse '1 year and 3 months' → 15 months"""
    import re
    months = 0
    year_match = re.search(r"(\d+)\s*year", term)
    month_match = re.search(r"(\d+)\s*month", term)

    if year_match:
        months += int(year_match.group(1)) * 12
    if month_match:
        months += int(month_match.group(1))
    return months or 1

def compute_loan_breakdown(loan_amount: Decimal, term: str) -> dict:
    """Reusable loan computation logic."""
    term = term.lower()

    if loan_amount <= 0:
        raise ValueError("Loan amount must be greater than zero.")

    if "100" in term:  # 100-day loan
        total_loan = loan_amount
        service_charge = total_loan * Decimal('0.07')
        cbu = total_loan * Decimal('0.10')
        insurance = total_loan * Decimal('0.01')
        total_amount = total_loan - service_charge - cbu - insurance
        amortization = loan_amount * Decimal('0.01')  # daily rate
        period_label = "Daily"
    else:
        months = extract_months(term)
        total_loan = loan_amount * ((Decimal('0.02') * months) + 1)
        service_charge = (total_loan - loan_amount) / 2
        cbu = (total_loan - loan_amount) / 2
        insurance = total_loan * Decimal('0.01')
        total_amount = total_loan - service_charge - cbu - insurance
        amortization = total_loan / months
        period_label = "Monthly"

    return {
        "totalPayable": round(total_loan, 2),
        "serviceCharge": round(service_charge, 2),
        "cbu": round(cbu, 2),
        "insurance": round(insurance, 2),
        "releaseAmount": round(total_amount, 2),
        "amortization": round(amortization, 2),
        "displayValue": period_label,
    }

def parse_duration(duration_str):
    # Lowercase for consistency
    duration_str = duration_str.lower()
    
    # Initialize all components to 0
    years = months = days = 0

    # Match years
    year_match = re.search(r'(\d+)\s*year', duration_str)
    if year_match:
        years = int(year_match.group(1))

    # Match months
    month_match = re.search(r'(\d+)\s*month', duration_str)
    if month_match:
        months = int(month_match.group(1))

    # Match days (optional if you use them)
    day_match = re.search(r'(\d+)\s*day', duration_str)
    if day_match:
        days = int(day_match.group(1))

    return years, months, days

def convert_date(years=0, months=0, days=0):
    years_to_days = years * 12 * 30
    months_to_days = months * 30
    total_days = years_to_days + months_to_days + days

    return total_days

def format_loan_term(loan):
    parts = []

    # Years
    if loan.loan_term_years:
        year_label = "years" if loan.loan_term_years > 1 else "year"
        parts.append(f"{loan.loan_term_years} {year_label}")

    # Months
    if loan.loan_term_months:
        month_label = "months" if loan.loan_term_months > 1 else "month"
        parts.append(f"{loan.loan_term_months} {month_label}")

    # Days
    if loan.loan_term_days:
        day_label = "days" if loan.loan_term_days > 1 else "day"
        parts.append(f"{loan.loan_term_days} {day_label}")

    # Join with "and" when needed
    if len(parts) > 1:
        return " and ".join([", ".join(parts[:-1]), parts[-1]]) if len(parts) > 2 else " and ".join(parts)
    elif parts:
        return parts[0]
    else:
        return "N/A"
