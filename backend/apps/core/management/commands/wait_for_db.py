"""``python manage.py wait_for_db [--timeout 60]``: block until PostgreSQL accepts connections.

Used by the container entrypoint so the app does not race the database at startup. Exit status 1
if the database is still unreachable after the timeout.
"""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import OperationalError, connections


class Command(BaseCommand):
    help = "Wait until the default database accepts connections."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--timeout", type=float, default=60.0, help="Seconds to wait.")
        parser.add_argument("--interval", type=float, default=1.0, help="Seconds between tries.")

    def handle(self, *args: Any, **options: Any) -> None:
        deadline = time.monotonic() + options["timeout"]
        attempt = 0
        while True:
            attempt += 1
            try:
                connections["default"].ensure_connection()
            except OperationalError as exc:
                if time.monotonic() >= deadline:
                    raise CommandError(
                        f"Database not reachable after {attempt} attempt(s): {exc}"
                    ) from exc
                self.stdout.write(f"Waiting for the database (attempt {attempt})…")
                time.sleep(options["interval"])
            else:
                self.stdout.write(self.style.SUCCESS("Database is ready."))
                return
