"""``python manage.py seed_demo_data [--reset]``"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.core.demo.seed_data import DEMO_PASSWORD, SEED_USERS
from apps.core.demo.service import DemoService
from apps.core.exceptions import ApplicationError


class Command(BaseCommand):
    help = (
        "Create the demo accounts, services and requests that are missing (safe to repeat). "
        "With --reset, wipe all data and restore the seed. Only allowed when ENABLE_DEMO_RESET is "
        "on: the demo accounts share a public password."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all requests, history, audit entries and non-seed accounts first.",
        )
        parser.add_argument(
            "--no-input",
            "--noinput",
            action="store_false",
            dest="interactive",
            help="Do not ask for confirmation before --reset.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.ENABLE_DEMO_RESET:
            raise CommandError(
                "Refusing to create demo accounts: they use a public password. "
                "Set ENABLE_DEMO_RESET=true to confirm this is a demo deployment."
            )
        try:
            if options["reset"]:
                if options["interactive"] and not self._confirmed():
                    raise CommandError("Reset cancelled.")
                DemoService.reset(actor=None, keep_token=None)
                self.stdout.write(self.style.SUCCESS("Demo data reset to the seed."))
            else:
                report = DemoService.seed()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Demo data ready: {report.users_created} account(s), "
                        f"{report.requests_created} request(s), "
                        f"{report.services_created} service(s) created."
                    )
                )
        except ApplicationError as exc:
            raise CommandError(f"{exc.error_code.value}: {exc.detail}") from exc
        usernames = ", ".join(seed.username for seed in SEED_USERS if seed.username)
        self.stdout.write(f"Staff sign-in usernames: {usernames} (password {DEMO_PASSWORD}).")

    def _confirmed(self) -> bool:
        answer = input(
            "This deletes ALL requests, history, audit entries and non-seed accounts. "
            "Type 'yes' to continue: "
        )
        return answer.strip().lower() == "yes"
