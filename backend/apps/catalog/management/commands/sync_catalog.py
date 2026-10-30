"""``python manage.py sync_catalog`` – load/refresh the built-in service catalogue."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.catalog.services import CatalogService


class Command(BaseCommand):
    help = (
        "Make the service catalogue in the database match apps/catalog/definitions.py. "
        "Idempotent; keeps each service's availability switch."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        report = CatalogService.sync_definitions()
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue synced: {report.created} created, {report.updated} updated."
            )
        )
