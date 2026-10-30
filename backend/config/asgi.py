"""ASGI entry point: ``uvicorn config.asgi:application`` (the container itself serves WSGI)."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()
