"""Vocabulary of the users app."""

from __future__ import annotations

from django.db import models


class UserRole(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    STAFF = "staff", "Staff"
    ADMIN = "admin", "Administrator"
