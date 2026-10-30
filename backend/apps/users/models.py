"""User accounts and access tokens (schema only).

One table holds the three kinds of account, because they authenticate and are referenced
identically; a CHECK constraint pins which columns each role may (and must) fill, so the database
itself rejects a "customer with a username" or a "staff member with no department".
"""

from __future__ import annotations

from typing import ClassVar

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import CheckConstraint, F, Q, UniqueConstraint
from django.utils import timezone

from apps.core.choices import Department
from apps.core.models import TimeStampedModel, UUIDModel
from apps.users.choices import UserRole

CUSTOMER_COLUMNS = ("full_name", "national_id", "phone", "postal_code", "address")
STAFF_COLUMNS = ("username", "name_fa", "name_en")


def _filled(columns: tuple[str, ...]) -> Q:
    return Q(**{f"{column}__isnull": False for column in columns})


def _empty(columns: tuple[str, ...]) -> Q:
    return Q(**{f"{column}__isnull": True for column in columns})


class UserManager(BaseUserManager["User"]):
    """Only what Django's auth machinery needs; accounts are created by ``apps.users.services``."""


class User(AbstractBaseUser, UUIDModel, TimeStampedModel):
    role = models.CharField(max_length=16, choices=UserRole.choices)
    is_active = models.BooleanField(default=True)

    # --- customers -------------------------------------------------------------------------
    full_name = models.CharField(max_length=100, null=True, blank=True)
    #: کد ملی. Personal data: see README "Security notes" for hardening options.
    national_id = models.CharField(max_length=10, null=True, blank=True)
    phone = models.CharField(max_length=11, null=True, blank=True)
    postal_code = models.CharField(max_length=10, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)

    # --- staff and administrators ----------------------------------------------------------
    username = models.CharField(max_length=20, null=True, blank=True)
    name_fa = models.CharField(max_length=60, null=True, blank=True)
    name_en = models.CharField(max_length=60, null=True, blank=True)
    #: The only departments a *staff* member may see or act on (empty for customers/admins:
    #: administrators are all-powerful by role, not by a list that could fall out of date).
    department_ids = ArrayField(
        models.CharField(max_length=32, choices=Department.choices),
        default=list,
        blank=True,
    )

    # Identity is the UUID: the natural "username" differs per role (national ID vs username)
    # and is unique only within its role, so it cannot be Django's USERNAME_FIELD.
    USERNAME_FIELD = "id"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()

    class Meta:
        constraints = [
            CheckConstraint(
                condition=(
                    (
                        Q(role=UserRole.CUSTOMER)
                        & _filled(CUSTOMER_COLUMNS)
                        & _empty(STAFF_COLUMNS)
                        & Q(department_ids__len=0)
                    )
                    | (
                        Q(role=UserRole.STAFF)
                        & _filled(STAFF_COLUMNS)
                        & _empty(CUSTOMER_COLUMNS)
                        & Q(department_ids__len__gte=1)
                    )
                    | (
                        Q(role=UserRole.ADMIN)
                        & _filled(STAFF_COLUMNS)
                        & _empty(CUSTOMER_COLUMNS)
                        & Q(department_ids__len=0)
                    )
                ),
                name="user_shape_matches_role",
            ),
            CheckConstraint(
                condition=Q(department_ids__contained_by=list(Department.values)),
                name="user_departments_known",
            ),
            CheckConstraint(
                condition=Q(national_id__isnull=True) | Q(national_id__regex=r"^[0-9]{10}$"),
                name="user_national_id_format",
            ),
            CheckConstraint(
                condition=Q(phone__isnull=True) | Q(phone__regex=r"^09[0-9]{9}$"),
                name="user_phone_format",
            ),
            CheckConstraint(
                condition=Q(postal_code__isnull=True) | Q(postal_code__regex=r"^[0-9]{10}$"),
                name="user_postal_code_format",
            ),
            # Lower-case by construction, which is what makes the plain unique index below a
            # case-insensitive one.
            CheckConstraint(
                condition=Q(username__isnull=True) | Q(username__regex=r"^[a-z][a-z0-9_]{2,19}$"),
                name="user_username_format",
            ),
            # NULLs never collide in a unique index, so each constraint applies only to the role
            # that fills the column.
            UniqueConstraint(fields=["national_id"], name="user_national_id_unique"),
            UniqueConstraint(fields=["phone"], name="user_phone_unique"),
            UniqueConstraint(fields=["username"], name="user_username_unique"),
        ]
        indexes = [
            # "which active staff can take work in department X" (assignee picker, queue scoping)
            GinIndex(fields=["department_ids"], name="user_department_ids_gin"),
            # the admin's team list: staff + admins, oldest first
            models.Index(fields=["role", "created_at"], name="user_role_created_idx"),
        ]

    def __str__(self) -> str:  # never include personal data in logs
        return f"{self.role}:{self.pk}"


class AccessToken(UUIDModel):
    """A server-side session: an opaque bearer token that can be revoked at any time.

    Only the SHA-256 of the token is stored, so a database leak does not leak usable credentials.
    The token itself carries 256 random bits, which is why a fast hash (not a password hash) is the
    right tool here.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_tokens",
        db_index=False,  # ``access_token_user_live_idx`` below starts with the user
    )
    key_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["key_hash"], name="access_token_key_hash_unique"),
            CheckConstraint(
                condition=Q(key_hash__regex=r"^[0-9a-f]{64}$"),
                name="access_token_key_hash_format",
            ),
            CheckConstraint(
                condition=Q(expires_at__gt=F("created_at")),
                name="access_token_expires_after_creation",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="access_token_user_live_idx"),
            models.Index(fields=["expires_at"], name="access_token_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"token:{self.pk}"
