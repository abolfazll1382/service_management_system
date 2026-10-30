"""Application configuration for `apps.requests`."""

from django.apps import AppConfig


class RequestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.requests"
    label = "requests"
