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