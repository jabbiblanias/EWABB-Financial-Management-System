import re


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
