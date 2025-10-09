#!/bin/bash

# 1. Use 'python3' to install dependencies
python3 -m pip install -r requirements.txt

# 2. Run the Tailwind build command
# NOTE: Replace 'theme' with your actual tailwind app name if different
python3 manage.py tailwind build

# 3. Collect static files
python3 manage.py collectstatic --noinput --clear

# 4. Run migrations
python3 manage.py migrate --noinput