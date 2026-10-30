"""Settings shared by every environment.

Everything that differs between environments lives in ``local``, ``production`` or ``test``.
Configuration comes from environment variables (12-factor) via django-environ; a ``.env`` file
next to ``manage.py`` is read when present, which is convenient for local development only.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_env_file = BASE_DIR / ".env"
if _env_file.is_file():
    environ.Env.read_env(str(_env_file))

# --- Core ------------------------------------------------------------------------------------

SECRET_KEY: str = env.str("DJANGO_SECRET_KEY", default="")
DEBUG: bool = False
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# There are no sessions, cookies, templates-as-pages or admin site: this is a bearer-token JSON
# API. ``django.contrib.auth`` stays installed only because DRF and AbstractBaseUser build on it.
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.users",
    "apps.catalog",
    "apps.requests",
    "apps.audit",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.RequestBodyLimitMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Only the OpenAPI UI renders a template; the API itself is pure JSON.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

# Routes are matched exactly as documented (with a trailing slash). Redirecting a POST to the
# slash variant would silently drop its body, so a wrong URL is a clean JSON 404 instead.
APPEND_SLASH = False

# --- Database --------------------------------------------------------------------------------

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"]["ATOMIC_REQUESTS"] = False  # services own their transactions explicitly
_statement_timeout_ms = env.int("DB_STATEMENT_TIMEOUT_MS", default=30_000)
if _statement_timeout_ms > 0:
    DATABASES["default"].setdefault("OPTIONS", {})["options"] = (
        f"-c statement_timeout={_statement_timeout_ms}"
    )

# --- Authentication / passwords --------------------------------------------------------------

AUTH_USER_MODEL = "users.User"
AUTHENTICATION_BACKENDS: list[str] = []  # tokens only: no session/model-backend login exists

# Argon2id with a project-tuned cost (see apps/core/hashers.py). PBKDF2 stays only so that hashes
# created elsewhere still verify and are upgraded on the next successful login.
PASSWORD_HASHERS = [
    "apps.core.hashers.PortalArgon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
ARGON2_TIME_COST: int = env.int("ARGON2_TIME_COST", default=2)
ARGON2_MEMORY_COST_KIB: int = env.int("ARGON2_MEMORY_COST_KIB", default=19_456)
ARGON2_PARALLELISM: int = env.int("ARGON2_PARALLELISM", default=1)

# The product's own password rule (8+ chars, a letter and a digit) is enforced by the serializers,
# because the frontend contract defines it; Django's validators are not used.
AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

ACCESS_TOKEN_TTL = timedelta(seconds=env.int("ACCESS_TOKEN_TTL_SECONDS", default=8 * 60 * 60))

# --- Internationalisation --------------------------------------------------------------------

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = False  # messages come from apps/core/messages.py, keyed by Accept-Language
USE_TZ = True

# --- Django REST framework -------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.users.authentication.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["apps.users.permissions.IsAuthenticatedActor"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["apps.core.parsers.StrictJSONParser"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": None,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "auth_login": env.str("THROTTLE_AUTH_LOGIN", default="20/min"),
        "auth_register": env.str("THROTTLE_AUTH_REGISTER", default="10/min"),
    },
    # How many reverse proxies sit in front of the app; decides which X-Forwarded-For entry is
    # the client for throttling. 0 = trust only REMOTE_ADDR (never trust a spoofable header).
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "National Citizen Services Portal API",
    "DESCRIPTION": (
        "Demo backend for the citizen services portal. Authentication is an opaque bearer token "
        "(`Authorization: Bearer <token>`). Errors always use `{code, detail, errors}`; "
        "field messages in `errors` are the frontend's validation dictionary keys."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api",
    # Pinned: the docs page must not change under us (and ``@latest`` would also be unreviewed
    # code).
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14",
    "SWAGGER_UI_FAVICON_HREF": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/favicon-32x32.png",
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.openapi.add_error_responses",
    ],
    # The same value sets appear in several serializers; give each one a single stable name.
    "ENUM_NAME_OVERRIDES": {
        "DepartmentEnum": "apps.core.choices.Department.choices",
        "RequestStatusEnum": "apps.requests.choices.RequestStatus.choices",
        "MessageVisibilityEnum": "apps.requests.choices.MessageVisibility.choices",
        "UserRoleEnum": "apps.users.choices.UserRole.choices",
        "AuditActionEnum": "apps.audit.choices.AuditAction.choices",
    },
}

# --- CORS ------------------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS: list[str] = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:3000", "http://127.0.0.1:3000"],
)
CORS_URLS_REGEX = r"^/api/.*$"
CORS_ALLOW_CREDENTIALS = False  # the token travels in a header, never in a cookie
# ``Accept-Language`` is CORS-safelisted already; it is listed so the intent is explicit, and
# ``X-Request-ID`` lets the frontend supply its own correlation id (the middleware keeps a sane
# one).
CORS_ALLOW_HEADERS = (*default_headers, "accept-language", "x-request-id")
CORS_EXPOSE_HEADERS = ["Retry-After", "X-Request-ID"]
CORS_PREFLIGHT_MAX_AGE = 600

# --- Caching (throttle counters) -------------------------------------------------------------

# LocMem is per-process: fine for one worker, but N workers/replicas each keep their own counters.
# Point CACHE_URL at a shared cache (e.g. Redis) in production if throttling must be exact.
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://portal-throttle")}

# --- Application settings --------------------------------------------------------------------

#: Largest request body the API accepts; every legitimate payload is a few hundred bytes.
API_MAX_BODY_BYTES: int = env.int("API_MAX_BODY_BYTES", default=64 * 1024)

#: ``POST /api/demo/reset/`` wipes ALL data back to the seed. Off unless explicitly enabled.
ENABLE_DEMO_RESET: bool = env.bool("ENABLE_DEMO_RESET", default=False)

#: Serve the OpenAPI schema and Swagger UI under /api/schema/ and /api/docs/.
ENABLE_API_DOCS: bool = env.bool("ENABLE_API_DOCS", default=False)

# --- Logging ---------------------------------------------------------------------------------

LOG_LEVEL: str = env.str("LOG_LEVEL", default="INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.requestid.RequestIDLogFilter"}},
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# --- Security headers (the HTTPS-related ones are in production.py) --------------------------

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
