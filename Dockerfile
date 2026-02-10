FROM python:3.11-slim

# Set work directory
WORKDIR /app


# Install system deps for pycairo
RUN apt-get update && apt-get install -y \
    build-essential \
    pkg-config \
    libcairo2-dev \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Default command
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
