"""WSGI config for the Date Planner backend."""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

logging.getLogger("date_planner.startup").info("Date Planner backend WSGI application initialized")
