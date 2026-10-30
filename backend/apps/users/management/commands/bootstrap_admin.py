"""``python manage.py bootstrap_admin --username admin --name-fa … --name-en …``

Creates the first administrator of a real (non-demo) deployment. The password is never taken from
the command line (it would show up in the process list and shell history): it is read from the
``BOOTSTRAP_ADMIN_PASSWORD`` environment variable, or prompted for twice. It is validated by the
same rules as every other password, and the account is created through the same code path as any
other account, so it is audited and hashed like one.
"""

from __future__ import annotations

import getpass
import os
from typing import Any

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from apps.audit.choices import AuditAction
from apps.audit.services import AuditService
from apps.core import messages as m
from apps.core.exceptions import ApplicationError
from apps.core.serializers import KeyedCharField
from apps.core.validators import username_validator
from apps.users.choices import UserRole
from apps.users.models import User
from apps.users.serializers import NewPasswordField
from apps.users.services import translate_user_integrity_error


class _BootstrapAdminSerializer(serializers.Serializer):  # type: ignore[type-arg]
    username = KeyedCharField(
        error_key=m.V_USERNAME,
        trim_whitespace=False,
        max_length=64,
        validators=[username_validator],
    )
    name_fa = KeyedCharField(error_key=m.V_NAMES, min_length=2, max_length=60)
    name_en = KeyedCharField(error_key=m.V_NAMES, min_length=2, max_length=60)
    password = NewPasswordField()


class Command(BaseCommand):
    help = "Create an administrator account (password from $BOOTSTRAP_ADMIN_PASSWORD or a prompt)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username", required=True)
        parser.add_argument("--name-fa", required=True, dest="name_fa")
        parser.add_argument("--name-en", required=True, dest="name_en")

    def handle(self, *args: Any, **options: Any) -> None:
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or self._prompt_password()
        form = _BootstrapAdminSerializer(
            data={
                "username": options["username"],
                "name_fa": options["name_fa"],
                "name_en": options["name_en"],
                "password": password,
            }
        )
        if not form.is_valid():
            problems = "; ".join(
                f"{field}: {', '.join(str(message) for message in messages)}"
                for field, messages in form.errors.items()
            )
            raise CommandError(f"Invalid input ({problems}).")
        data = form.validated_data

        now = timezone.now()
        try:
            with transaction.atomic():
                admin = User(
                    role=UserRole.ADMIN,
                    username=data["username"],
                    name_fa=data["name_fa"],
                    name_en=data["name_en"],
                    password=make_password(data["password"]),
                    created_at=now,
                    updated_at=now,
                )
                admin.save(force_insert=True)
                AuditService.record(
                    actor=admin,
                    action=AuditAction.STAFF_CREATED,
                    target=admin.username or "",
                    at=now,
                )
        except IntegrityError as exc:
            translated = translate_user_integrity_error(exc)
            if translated is None:
                raise
            error: ApplicationError = translated
            raise CommandError(
                f"{error.error_code.value}: that username is already taken."
            ) from exc
        self.stdout.write(self.style.SUCCESS(f"Administrator '{admin.username}' created."))

    @staticmethod
    def _prompt_password() -> str:
        first = getpass.getpass("Password: ")
        if first != getpass.getpass("Password (again): "):
            raise CommandError("The two passwords do not match.")
        return first
