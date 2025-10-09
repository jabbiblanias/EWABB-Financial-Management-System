#!/bin/bash

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Run Django-Tailwind's production build command
# This command compiles and purges your final CSS file into your static files directory.
# Replace 'theme' with the name of your tailwind app if it's different.
python manage.py tailwind build --production

# 3. Collect all static files (including the compiled Tailwind CSS)
python manage.py collectstatic --noinput --clear

# 4. (Optional) Run migrations
python manage.py migrate --noinput