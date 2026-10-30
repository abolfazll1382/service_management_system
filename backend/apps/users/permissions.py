"""DRF permission classes: the *coarse*, role-level gate in front of each view.

They answer "may this kind of caller use this endpoint at all?" and run before any input is
validated. Object-level decisions (this request, that department) are made by the services, which
call the same :func:`apps.users.policies.can`.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from apps.users.choices import UserRole
from apps.users.models import User
from apps.users.policies import Action, can


def current_actor(request: Request) -> User | None:
    """The signed-in account, or ``None`` for an anonymous caller.

    DRF types ``request.user`` as "a ``User`` or an ``AnonymousUser``"; this narrows it once, here,
    instead of at every call site.
    """
    user = request.user
    return user if isinstance(user, User) and user.is_authenticated else None


def require_actor(request: Request) -> User:
    """The signed-in account behind a request that has already passed an authentication gate.

    Views behind :class:`IsAuthenticatedActor` (the project default) can rely on it; should one
    ever be reached anonymously, the caller gets the contract's ``unauthenticated`` error rather
    than an ``AttributeError``.
    """
    actor = current_actor(request)
    if actor is None:
        # Imported here, not at the top: this module is the default permission class, so it is
        # loaded while DRF is still importing itself, and the exceptions module needs
        # ``rest_framework.views``.
        from apps.core.exceptions import UnauthenticatedError

        raise UnauthenticatedError()
    return actor


class IsAuthenticatedActor(BasePermission):
    """Default for every endpoint: a valid, unexpired token of an *active* account."""

    def has_permission(self, request: Request, view: Any) -> bool:
        return current_actor(request) is not None


class IsCustomer(IsAuthenticatedActor):
    """Applicants only (e.g. "my requests")."""

    def has_permission(self, request: Request, view: Any) -> bool:
        actor = current_actor(request)
        return actor is not None and actor.role == UserRole.CUSTOMER


def allows(action: Action) -> type[BasePermission]:
    """Permission class granting access iff the shared policy allows ``action`` (no resource).

    ``permission_classes = [allows(Action.STAFF_MANAGE)]`` reads exactly like the rule it enforces.
    """

    class ActionPermission(IsAuthenticatedActor):
        def has_permission(self, request: Request, view: Any) -> bool:
            return super().has_permission(request, view) and can(current_actor(request), action)

    ActionPermission.__name__ = ActionPermission.__qualname__ = f"Allows[{action.value}]"
    return ActionPermission
