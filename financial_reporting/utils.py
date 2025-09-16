import re
from django.db.models import Model


def generate_unique_name(model: Model, field: str, base_name: str) -> str:
    """
    Generate a unique name by appending (n) if the name already exists.

    :param model: Django model class (e.g., Report)
    :param field: Field name to check uniqueness (e.g., 'title')
    :param base_name: Desired base name
    :return: Unique name string
    """
    # Check if the exact name already exists
    existing = model.objects.filter(**{field: base_name})
    if not existing.exists():
        return base_name

    # Regex to match names like "Report (1)", "Report (2)"
    pattern = re.escape(base_name) + r'(?: \((\d+)\))?$'
    similar_names = model.objects.filter(**{f"{field}__regex": pattern}).values_list(field, flat=True)

    numbers = []
    for name in similar_names:
        match = re.match(rf'^{re.escape(base_name)}(?: \((\d+)\))?$', name)
        if match and match.group(1):
            numbers.append(int(match.group(1)))

    next_number = max(numbers, default=0) + 1
    return f"{base_name} ({next_number})"