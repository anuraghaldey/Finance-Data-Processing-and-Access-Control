#!/bin/bash
set -e

echo "Running database migrations..."
flask db upgrade

echo "Seeding database..."
python seeds/seed.py

echo "Starting Gunicorn..."
exec gunicorn -c gunicorn.conf.py run:app
