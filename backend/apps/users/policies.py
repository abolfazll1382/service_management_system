"""Who may do what: the single source of truth for authorisation.

A direct port of ``src/lib/auth/policies.ts``. Every decision is a pure function over
``(who, what, which resource)`` with *deny by default*: anything not explicitly allowed is denied.
Services call :func:`can` to refuse an action; the OpenAPI/README matrix and the exhaustive policy
tests are derived from the same rules. No database access happens here, so the functions are
trivially testable with unsaved ``User`` instances.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from apps.core.choices import DEPARTMENT_IDS
from apps.users.choices import UserRole

if TYPE_CHECKING:
    from apps.users.models import User


class Action(StrEnum):
    CONSOLE_ACCESS = "console.access"
    REQUEST_CREATE = "request.create"
    REQUEST_READ = "request.read"
    REQUEST_COMMENT = "request.comment"
    REQUEST_COMMENT_INTERNAL = "request.comment_internal"
    REQUEST_TRANSITION = "request.transition"
    REQUEST_ASSIGN = "request.assign"
    STAFF_MANAGE = "staff.manage"
    SERVICE_MANAGE = "service.manage"
    AUDIT_READ = "audit.read"
    DEMO_RESET = "demo.reset"


@dataclass(frozen=True, slots=True)
class PolicyResource:
    """The thing an action is aimed at. Either part may be unknown."""

    department_id: str | None = None  # the department a request belongs to
    owner_id: UUID | None = None  # the customer who owns a request


NO_RESOURCE = PolicyResource()

#: Actions a *staff* member may take on a request, always scoped to their departments.
_DEPARTMENT_SCOPED = frozenset(
    {
        Action.REQUEST_READ,
        Action.REQUEST_COMMENT,
        Action.REQUEST_COMMENT_INTERNAL,
        Action.REQUEST_TRANSITION,
        Action.REQUEST_ASSIGN,
    }
)


def _staff_can(actor: User, action: Action, resource: PolicyResource) -> bool:
    if action is Action.CONSOLE_ACCESS:
        return True
    if action in _DEPARTMENT_SCOPED:
        return resource.department_id is not None and resource.department_id in actor.department_ids
    return False


def _customer_can(actor: User, action: Action, resource: PolicyResource) -> bool:
    if action is Action.REQUEST_CREATE:
        return True
    if action in (Action.REQUEST_READ, Action.REQUEST_COMMENT):
        # Customers only ever touch their own requests, never somebody else's.
        return resource.owner_id is not None and resource.owner_id == actor.id
    return False


def can(actor: User | None, action: Action, resource: PolicyResource = NO_RESOURCE) -> bool:
    """May ``actor`` perform ``action`` on ``resource``? ``None``/inactive actors may do nothing."""
    if actor is None or not actor.is_active:
        return False
    if actor.role == UserRole.ADMIN:
        # Admins run the system but are not applicants, so they cannot file requests.
        return action is not Action.REQUEST_CREATE
    if actor.role == UserRole.STAFF:
        return _staff_can(actor, action, resource)
    if actor.role == UserRole.CUSTOMER:
        return _customer_can(actor, action, resource)
    return False


def visible_departments(actor: User | None) -> tuple[str, ...]:
    """The departments whose requests ``actor`` may see at all."""
    if actor is None or not actor.is_active:
        return ()
    if actor.role == UserRole.ADMIN:
        return DEPARTMENT_IDS
    if actor.role == UserRole.STAFF:
        return tuple(actor.department_ids)
    return ()


def can_assign_to(actor: User | None, assignee: User | None, department_id: str) -> bool:
    """May ``actor`` assign a request of ``department_id`` to ``assignee`` (``None`` = unassign)?

    The assignee must be an active staff member of that department. Staff can only assign to
    themselves (i.e. claim); administrators can assign to anyone eligible.
    """
    if actor is None or not can(
        actor, Action.REQUEST_ASSIGN, PolicyResource(department_id=department_id)
    ):
        return False
    if assignee is None:
        return True  # un-assigning
    if assignee.role != UserRole.STAFF or not assignee.is_active:
        return False
    if department_id not in assignee.department_ids:
        return False
    return actor.role == UserRole.ADMIN or actor.id == assignee.id
