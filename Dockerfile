# Dockerfile
FROM python:3.12-slim

# Install system dependencies (xhtml2pdf, pycairo, etc.)
RUN apt-get update && apt-get install -y \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "ewabb_financial_management_system_with_forecasting.wsgi:application", "--bind", "0.0.0.0:8000"]
