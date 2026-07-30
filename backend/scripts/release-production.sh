#!/bin/sh
set -eu

echo "[release] Checking production settings..."
# The initial HSTS rollout intentionally leaves subdomains and preload disabled.
# Django still prints those warnings for operator review; project-specific checks
# below keep unsafe transport and secret settings release-blocking errors.
python manage.py check --deploy

echo "[release] Verifying the application database role..."
python manage.py verify_database_role

echo "[release] Applying database migrations..."
python manage.py migrate --noinput

echo "[release] Collecting backend static files..."
python manage.py collectstatic --noinput --clear

echo "[release] Production release step completed."
