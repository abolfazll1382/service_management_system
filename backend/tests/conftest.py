"""Fixtures shared by the whole suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.cache import cache

from apps.core.demo.service import DemoService


@pytest.fixture
def demo(db: None) -> None:
    """The seeded demo data (accounts, services, requests) inside the test's transaction."""
    DemoService.seed()


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    """Throttle counters live in the cache and must never leak from one test into the next."""
    cache.clear()
    yield
    cache.clear()
