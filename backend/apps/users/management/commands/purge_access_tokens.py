"""``python manage.py purge_access_tokens [--older-than-days 7]``

Expired and revoked tokens are already useless; this deletes them (after a grace period, which keeps
recent sessions around for investigation). Run it from a scheduler, e.g. daily.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q
from django.utils import timezone

from apps.users.models import AccessToken


class Command(BaseCommand):
    help = "Delete expired or revoked access tokens older than the grace period."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=7,
            help="Grace period after expiry/revocation (default: 7).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - timedelta(days=max(0, options["older_than_days"]))
        deleted, _ = AccessToken.objects.filter(
            Q(expires_at__lt=cutoff) | Q(revoked_at__lt=cutoff)
        ).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} access token(s)."))
