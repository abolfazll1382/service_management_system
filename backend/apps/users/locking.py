"""Row locks on user accounts.

Why accounts are locked at all: an administrator can deactivate a staff member or change their
departments *while that person is mid-action* (claiming a request, say). Without a lock, the claim
could commit after the administrator's "release this person's open work" step has already run,
leaving a request assigned to someone who can no longer touch it. Every mutation therefore:

1. locks the acting user (and any user it targets) ``FOR NO KEY UPDATE`` — always in primary-key
   order, so two transactions can never wait on each other in a cycle;
2. re-reads the actor under the lock and refuses if it is no longer active;
3. only then locks the request row.

Lock order across the codebase is therefore always *users (by id) → request*.
``NO KEY UPDATE`` conflicts with itself but not with the ``KEY SHARE`` locks that inserting rows
referencing a user takes, so unrelated writes are not blocked.
"""

from __future__ import annotations

from uuid import UUID

from apps.core.exceptions import UnauthenticatedError
from apps.users.models import User


def lock_users(*user_ids: UUID | None) -> dict[UUID, User]:
    """Lock the existing rows among ``user_ids`` (in id order) and return them keyed by id.

    Must be called inside ``transaction.atomic()`` (Django raises otherwise). Unknown ids are
    simply absent from the result.
    """
    ids = sorted({user_id for user_id in user_ids if user_id is not None})
    if not ids:
        return {}
    rows = User.objects.select_for_update(no_key=True).filter(pk__in=ids).order_by("pk")
    return {user.pk: user for user in rows}


def lock_active_actor(actor: User, *also: UUID | None) -> tuple[User, dict[UUID, User]]:
    """Lock ``actor`` plus ``also`` and return the *fresh* actor row with all locked rows.

    The token that authenticated the call was valid when the request started; this re-check makes
    "deactivated a moment ago" behave like "no session": ``unauthenticated``.
    """
    locked = lock_users(actor.pk, *also)
    fresh = locked.get(actor.pk)
    if fresh is None or not fresh.is_active:
        raise UnauthenticatedError()
    return fresh, locked
