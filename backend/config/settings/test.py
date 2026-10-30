"""Settings for the automated test-suite."""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "postgres://portal:portal@localhost:5432/portal")
os.environ.setdefault(
    "DJANGO_SECRET_KEY", "django-insecure-test-key-not-used-anywhere-else-0123456789"
)

from .base import *

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

# Real hashing is deliberately slow; one test (tests/test_passwords.py) exercises the production
# hasher explicitly, everything else uses a fast one.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

ENABLE_DEMO_RESET = True
ENABLE_API_DOCS = True

# Throttling is switched on per-test where it is the subject; otherwise it must not interfere.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {"auth_login": "100000/min", "auth_register": "100000/min"},
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
LOGGING["root"]["level"] = "WARNING"  # type: ignore[index]
