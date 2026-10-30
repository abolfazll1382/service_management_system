"""Application configuration for `apps.users`."""

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    label = "users"

    def ready(self) -> None:
        # Registers the OpenAPI description of the bearer scheme (an import side effect).
        from apps.users import schema  # noqa: F401
