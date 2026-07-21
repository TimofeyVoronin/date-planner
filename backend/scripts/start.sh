#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import psycopg

connection_parameters = {
    "dbname": os.getenv("POSTGRES_DB", "date_planner"),
    "user": os.getenv("POSTGRES_USER", "date_planner"),
    "password": os.getenv("POSTGRES_PASSWORD", "date_planner_dev"),
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "connect_timeout": 3,
}

for attempt in range(1, 31):
    try:
        with psycopg.connect(**connection_parameters):
            print("[startup] PostgreSQL is ready.", flush=True)
            break
    except psycopg.OperationalError as error:
        if attempt == 30:
            raise SystemExit("[startup] PostgreSQL did not become ready in time.") from error
        print(
            f"[startup] Waiting for PostgreSQL ({attempt}/30)...",
            flush=True,
        )
        time.sleep(2)
PY

echo "[startup] Applying database migrations..."
python manage.py migrate --noinput

echo "[startup] Starting Date Planner backend on 0.0.0.0:8000..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --access-logfile - \
    --error-logfile -
