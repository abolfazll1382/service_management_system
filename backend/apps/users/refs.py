"""``ActorRef``: a lightweight, denormalised "who did this", frozen at the time of the action.

Customers cannot read the users table (privacy), so timeline events and audit rows carry their own
copy of the actor's role and names. Customers have a single plain name, used for both languages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from apps.users.choices import UserRole

if TYPE_CHECKING:
    from apps.users.models import User


@dataclass(frozen=True, slots=True)
class ActorSnapshot:
    role: str
    name_fa: str
    name_en: str


def snapshot_of(user: User) -> ActorSnapshot:
    """The snapshot to store next to a row that records ``user``'s action."""
    if user.role == UserRole.CUSTOMER:
        name = user.full_name or ""
        return ActorSnapshot(role=user.role, name_fa=name, name_en=name)
    return ActorSnapshot(role=user.role, name_fa=user.name_fa or "", name_en=user.name_en or "")


def actor_ref(user_id: UUID | str, role: str, name_fa: str, name_en: str) -> dict[str, Any]:
    """The wire shape of an ``ActorRef``: ``{id, role, name: {fa, en}}``."""
    return {"id": str(user_id), "role": role, "name": {"fa": name_fa, "en": name_en}}


def actor_ref_of(user: User) -> dict[str, Any]:
    """``ActorRef`` of a live user row (used for a request's *current* assignee)."""
    snap = snapshot_of(user)
    return actor_ref(user.id, snap.role, snap.name_fa, snap.name_en)
