#!/bin/bash

python manage.py makemigrations events
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn --bind 0.0.0.0:8000 FurConnectApp.wsgi:application