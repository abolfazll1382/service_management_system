"""``python manage.py migrate_locked``: ``migrate``, but replicas starting together take turns.

Django's ``migrate`` is not safe to run from two processes at once (both may try to create the
same table). This wraps it in a PostgreSQL *session* advisory lock: the first process migrates,
the others wait, then find nothing left to do. If the holder dies, PostgreSQL releases the lock.
"""

from __future__ import annotations

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

#: Distinct from the seeding lock in ``apps.core.demo.service``.
MIGRATION_LOCK_KEY = 0x5EED_B00C


class Command(BaseCommand):
    help = "Apply migrations while holding a PostgreSQL advisory lock (safe for parallel starts)."

    def handle(self, *args: Any, **options: Any) -> None:
        verbosity = options["verbosity"]
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [MIGRATION_LOCK_KEY])
        try:
            call_command(
                "migrate",
                interactive=False,
                verbosity=verbosity,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [MIGRATION_LOCK_KEY])
