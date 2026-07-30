#!/bin/sh
set -eu

echo "[startup] Starting Date Planner backend on 0.0.0.0:8000..."
# The production Compose topology never publishes this port. Caddy is the only
# external peer and overwrites X-Forwarded-* before Gunicorn receives a request.
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --graceful-timeout "${GUNICORN_GRACEFUL_TIMEOUT:-30}" \
    --keep-alive 5 \
    --worker-tmp-dir /tmp \
    --forwarded-allow-ips '*' \
    --no-control-socket \
    --access-logfile - \
    --access-logformat '{"event":"http_response","method":"%(m)s","status":"%(s)s","bytes":"%(b)s","duration_us":"%(D)s"}' \
    --error-logfile - \
    --capture-output
