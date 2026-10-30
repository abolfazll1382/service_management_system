"""Production settings.

Secrets and hosts are mandatory: the process refuses to start without them rather than falling
back to an insecure default.
"""

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured

from .base import *
from .base import ALLOWED_HOSTS as _CONFIGURED_HOSTS
from .base import SECRET_KEY as _CONFIGURED_SECRET
from .base import env

DEBUG = False

if len(_CONFIGURED_SECRET) < 50 or _CONFIGURED_SECRET.startswith("django-insecure"):
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set to a unique, random value of at least 50 characters."
    )
if not _CONFIGURED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list the host names this API serves.")

# Loopback is always allowed so the container health check can reach the app by address.
ALLOWED_HOSTS = [*_CONFIGURED_HOSTS, "127.0.0.1", "localhost"]

# --- HTTPS -----------------------------------------------------------------------------------

# TLS normally terminates at a reverse proxy / load balancer that sets X-Forwarded-Proto.
if env.bool("DJANGO_BEHIND_PROXY", default=True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # probes talk plain HTTP inside the cluster
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
if SECURE_HSTS_PRELOAD and (SECURE_HSTS_SECONDS < 31_536_000 or not SECURE_HSTS_INCLUDE_SUBDOMAINS):
    raise ImproperlyConfigured(
        "DJANGO_SECURE_HSTS_PRELOAD needs DJANGO_SECURE_HSTS_SECONDS >= 31536000 and "
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true; browsers' preload lists reject anything less."
    )
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# `manage.py check --deploy` would otherwise nag about two things that are deliberate here:
#   security.W003  CsrfViewMiddleware is absent -> there is no cookie/session authentication to
#                  forge a cross-site request against (the token is sent in a header by script).
#                  The two *_COOKIE_SECURE flags above are set anyway so the check stays quiet if
#                  cookies are ever introduced.
#   security.W021  HSTS preload is off. Joining a browser preload list is a commitment that covers
#                  the whole registrable domain and is slow to undo, so it is an explicit opt-in
#                  (DJANGO_SECURE_HSTS_PRELOAD=true) made by whoever owns the domain, not a default.
SILENCED_SYSTEM_CHECKS = ["security.W003", "security.W021"]
