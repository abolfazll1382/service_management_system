"""Reads over the catalogue."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.catalog.models import Service


class CatalogSelector:
    @staticmethod
    def listings() -> QuerySet[Service]:
        """Every service in display order (the catalogue is public, so nothing is filtered)."""
        return Service.objects.order_by("position", "id")

    @staticmethod
    def get(service_id: str) -> Service | None:
        return Service.objects.filter(pk=service_id).first()
