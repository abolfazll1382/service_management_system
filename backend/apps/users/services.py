"""Mutations of accounts and sessions: registration, sign-in/out, and staff management.

All business rules and multi-row invariants live here (models are schema only). Each public method
is one unit of work: it validates its preconditions, changes state inside ``transaction.atomic``,
writes its audit entry in that same transaction, and raises a domain error on refusal.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.choices import AuditAction
from apps.audit.services import AuditService
from apps.core.db import violated_constraint
from apps.core.exceptions import (
    ApplicationError,
    ForbiddenError,
    InvalidCredentialsError,
    NationalIdTakenError,
    NotFoundError,
    PhoneTakenError,
    UsernameTakenError,
)
from apps.core.ids import parse_uuid
from apps.core.persian import mask_national_id
from apps.requests.services import RequestWorkflowService
from apps.users.authentication import hash_token
from apps.users.choices import UserRole
from apps.users.locking import lock_active_actor, lock_users
from apps.users.models import AccessToken, User
from apps.users.policies import Action, can
from apps.users.selectors import UserSelector

_USERNAME_SHAPE = re.compile(r"[a-z][a-z0-9_]{2,19}")
_UNLOGGABLE_USERNAME = "(invalid)"


@dataclass(frozen=True, slots=True)
class AuthResult:
    """What a successful register/sign-in hands back: the bearer token and who it belongs to."""

    token: str
    user: User


@lru_cache(maxsize=1)
def _decoy_hash() -> str:
    """Verified against when the account does not exist, so "no such user" and "wrong password"
    cost the same and give the same answer: the response never reveals which it was."""
    return make_password(secrets.token_urlsafe(16))


def _issue_token(user: User, now: datetime) -> str:
    raw = secrets.token_hex(32)  # 256 random bits; only its SHA-256 is stored
    AccessToken.objects.create(
        user=user,
        key_hash=hash_token(raw),
        created_at=now,
        expires_at=now + settings.ACCESS_TOKEN_TTL,
    )
    return raw


def translate_user_integrity_error(error: IntegrityError) -> ApplicationError | None:
    """Turn a lost race on a unique index into the error the pre-check would have raised."""
    constraint = violated_constraint(error)
    if constraint == "user_national_id_unique":
        return NationalIdTakenError()
    if constraint == "user_phone_unique":
        return PhoneTakenError()
    if constraint == "user_username_unique":
        return UsernameTakenError()
    return None


class AuthService:
    @staticmethod
    def register(
        *,
        full_name: str,
        national_id: str,
        phone: str,
        postal_code: str,
        address: str,
        password: str,
    ) -> AuthResult:
        """Create a customer account and sign them in. Only ever creates the *customer* role:
        nothing a client sends can make an administrator or staff member."""
        hashed = make_password(password)  # deliberately slow: done before the transaction opens
        now = timezone.now()
        try:
            with transaction.atomic():
                if User.objects.filter(national_id=national_id).exists():
                    raise NationalIdTakenError()
                if User.objects.filter(phone=phone).exists():
                    raise PhoneTakenError()
                user = User(
                    role=UserRole.CUSTOMER,
                    full_name=full_name,
                    national_id=national_id,
                    phone=phone,
                    postal_code=postal_code,
                    address=address,
                    password=hashed,
                    last_login=now,
                    created_at=now,
                    updated_at=now,
                )
                user.save(force_insert=True)
                AuditService.record(actor=user, action=AuditAction.AUTH_REGISTER, at=now)
                token = _issue_token(user, now)
        except IntegrityError as exc:
            translated = translate_user_integrity_error(exc)
            if translated is None:
                raise
            raise translated from exc
        return AuthResult(token=token, user=user)

    @staticmethod
    def login_customer(*, national_id: str, password: str) -> AuthResult:
        """Customers sign in with national ID + password (shape-checked by the caller, not the
        checksum, so a mistyped ID gets the same answer as a wrong password)."""
        user = UserSelector.customer_by_national_id(national_id)
        return AuthService._login(user, password, failure_target=mask_national_id(national_id))

    @staticmethod
    def login_staff(*, username: str, password: str) -> AuthResult:
        """Staff and administrators share this door; usernames are case-insensitive."""
        wanted = username.strip().lower()
        user = UserSelector.staff_account_by_username(wanted)
        # A password typed into the username box is a classic mistake; never copy arbitrary text
        # into the audit log, only things shaped like a real username.
        loggable = wanted if _USERNAME_SHAPE.fullmatch(wanted) else _UNLOGGABLE_USERNAME
        return AuthService._login(user, password, failure_target=loggable)

    @staticmethod
    def _login(user: User | None, password: str, *, failure_target: str) -> AuthResult:
        if user is not None:
            password_ok = user.check_password(password)
        else:
            password_ok = False
            check_password(password, _decoy_hash())  # equal work, result discarded

        session = (
            AuthService._open_session(user) if user and user.is_active and password_ok else None
        )
        if session is None:
            # Recorded here, *outside* any transaction: an audit row written inside one that is
            # then abandoned would vanish together with the failure it describes.
            AuditService.record(
                actor=None, action=AuditAction.AUTH_LOGIN_FAILED, target=failure_target
            )
            raise InvalidCredentialsError()
        return session

    @staticmethod
    def _open_session(user: User) -> AuthResult | None:
        now = timezone.now()
        with transaction.atomic():
            # Serialises with an administrator switching this account off: either the account is
            # already inactive here (sign-in refused) or the deactivation runs afterwards and
            # revokes the token minted below.
            locked = lock_users(user.pk).get(user.pk)
            if locked is None or not locked.is_active:
                return None
            locked.last_login = now
            locked.save(update_fields=["last_login"])
            AccessToken.objects.filter(user=locked).filter(
                Q(expires_at__lte=now) | Q(revoked_at__isnull=False)
            ).delete()  # keeps each account's token history bounded
            token = _issue_token(locked, now)
            AuditService.record(actor=locked, action=AuditAction.AUTH_LOGIN, at=now)
        return AuthResult(token=token, user=locked)

    @staticmethod
    def logout(*, raw_token: str | None) -> None:
        """Revoke the presented token. Idempotent: an unknown/expired/already-revoked token is
        simply a no-op, so a client can always "sign out" without learning anything."""
        if not raw_token:
            return
        AccessToken.objects.filter(key_hash=hash_token(raw_token), revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )


class StaffService:
    """Team management: administrators create staff and change their access."""

    @staticmethod
    def create(
        *,
        actor: User,
        name_fa: str,
        name_en: str,
        username: str,
        password: str,
        department_ids: Sequence[str],
    ) -> User:
        if not can(actor, Action.STAFF_MANAGE):
            raise ForbiddenError()
        hashed = make_password(password)
        now = timezone.now()
        try:
            with transaction.atomic():
                admin, _ = lock_active_actor(actor)
                if not can(admin, Action.STAFF_MANAGE):
                    raise ForbiddenError()
                if User.objects.filter(username=username).exists():
                    raise UsernameTakenError()
                user = User(
                    role=UserRole.STAFF,
                    username=username,
                    name_fa=name_fa,
                    name_en=name_en,
                    department_ids=list(dict.fromkeys(department_ids)),
                    password=hashed,
                    created_at=now,
                    updated_at=now,
                )
                user.save(force_insert=True)
                AuditService.record(
                    actor=admin, action=AuditAction.STAFF_CREATED, target=username, at=now
                )
        except IntegrityError as exc:
            translated = translate_user_integrity_error(exc)
            if translated is None:
                raise
            raise translated from exc
        return user

    @staticmethod
    def update(
        *,
        actor: User,
        staff_id: str,
        department_ids: Sequence[str],
        is_active: bool,
    ) -> User:
        """Change a staff member's departments and/or switch the account on or off.

        Administrator and customer accounts cannot be edited here, so nobody can lock the last
        administrator out of the system through the API. Changes apply immediately (no re-login):
        a deactivated person's tokens are revoked, and open requests assigned to someone who can no
        longer touch them are released back to the queue (closed history is kept).
        """
        if not can(actor, Action.STAFF_MANAGE):
            raise ForbiddenError()
        target_id = parse_uuid(staff_id)
        now = timezone.now()
        with transaction.atomic():
            admin, locked = lock_active_actor(actor, target_id)
            if not can(admin, Action.STAFF_MANAGE):
                raise ForbiddenError()
            target = locked.get(target_id) if target_id is not None else None
            if target is None:
                raise NotFoundError()
            if target.role != UserRole.STAFF:
                raise ForbiddenError()

            target.department_ids = list(dict.fromkeys(department_ids))
            target.is_active = is_active
            target.updated_at = now
            target.save(update_fields=["department_ids", "is_active", "updated_at"])

            RequestWorkflowService.release_open_work_of(staff=target, by=admin, at=now)
            if not is_active:
                AccessToken.objects.filter(user=target, revoked_at__isnull=True).update(
                    revoked_at=now
                )
            AuditService.record(
                actor=admin,
                action=AuditAction.STAFF_UPDATED,
                target=target.username or "",
                at=now,
            )
        return target
