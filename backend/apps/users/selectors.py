"""Reads over user accounts. Pure queries: no writes, no authorisation decisions."""

from __future__ import annotations

from django.db.models import QuerySet

from apps.users.choices import UserRole
from apps.users.models import User


class UserSelector:
    @staticmethod
    def customer_by_national_id(national_id: str) -> User | None:
        return User.objects.filter(role=UserRole.CUSTOMER, national_id=national_id).first()

    @staticmethod
    def staff_account_by_username(username: str) -> User | None:
        """Staff *or* administrator (they share one sign-in door; customers have no username)."""
        return User.objects.filter(
            role__in=(UserRole.STAFF, UserRole.ADMIN), username=username.lower()
        ).first()

    @staticmethod
    def staff_accounts() -> QuerySet[User]:
        """Everyone who may sign in to the console, oldest first."""
        return User.objects.filter(role__in=(UserRole.STAFF, UserRole.ADMIN)).order_by(
            "created_at", "username"
        )

    @staticmethod
    def active_staff_of_department(department_id: str) -> QuerySet[User]:
        """Active staff granted ``department_id`` (candidates for assignment), oldest first."""
        return User.objects.filter(
            role=UserRole.STAFF, is_active=True, department_ids__contains=[department_id]
        ).order_by("created_at", "username")
