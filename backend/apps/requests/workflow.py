"""The status state machine (pure functions, no database).

A port of ``src/lib/domain/workflow.ts``. Defining the legal moves as data means the service only
accepts valid next steps: a client that skips the UI still cannot jump from "pending review"
straight to "approved".
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from apps.requests.choices import RequestStatus

S = RequestStatus

ALLOWED_TRANSITIONS: Final[Mapping[str, tuple[str, ...]]] = {
    S.PENDING_REVIEW: (S.IN_PROGRESS, S.REJECTED),
    S.IN_PROGRESS: (S.NEEDS_CORRECTION, S.APPROVED, S.REJECTED),
    S.NEEDS_CORRECTION: (S.IN_PROGRESS, S.REJECTED),
    S.APPROVED: (S.CLOSED,),
    S.REJECTED: (S.CLOSED,),
    S.CLOSED: (),
}

#: Still needs somebody's attention.
OPEN_STATUSES: Final[tuple[str, ...]] = (S.PENDING_REVIEW, S.IN_PROGRESS, S.NEEDS_CORRECTION)

#: Decisions the applicant must be able to act on come with a reason: a rejection that says
#: nothing, or a correction request that doesn't say what to correct, is useless.
NOTE_REQUIRED: Final[frozenset[str]] = frozenset({S.REJECTED, S.NEEDS_CORRECTION})


def next_statuses(from_status: str) -> tuple[str, ...]:
    return ALLOWED_TRANSITIONS[from_status]


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS[from_status]


def is_closed(status: str) -> bool:
    return status == S.CLOSED


def is_open(status: str) -> bool:
    return status in OPEN_STATUSES


def requires_note(to_status: str) -> bool:
    return to_status in NOTE_REQUIRED
