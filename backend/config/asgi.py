"""ASGI config for the Date Planner backend."""

import logging
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

logging.getLogger("date_planner.startup").info("Date Planner backend ASGI application initialized")
