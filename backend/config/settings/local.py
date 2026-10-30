"""Local development settings: verbose, permissive, demo tooling on."""

from __future__ import annotations

import os

# Convenient defaults so ``python manage.py runserver`` works against the compose/local database
# without a .env file. Real environment variables always win (setdefault).
os.environ.setdefault("DATABASE_URL", "postgres://portal:portal@localhost:5432/portal")
os.environ.setdefault("DJANGO_SECRET_KEY", "django-insecure-local-development-key-do-not-deploy")

from .base import *
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

ENABLE_DEMO_RESET = env.bool("ENABLE_DEMO_RESET", default=True)
ENABLE_API_DOCS = env.bool("ENABLE_API_DOCS", default=True)
