#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install requirements
pip install -r requirements.txt

# 2. Collect static files (CSS/Images)
python manage.py collectstatic --no-input

# 3. Migrate Database
python manage.py migrate