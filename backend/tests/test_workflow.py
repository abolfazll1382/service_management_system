"""The status state machine (port of the frontend's ``workflow.test.ts``)."""

from __future__ import annotations

import pytest

from apps.requests.choices import RequestStatus
from apps.requests.workflow import (
    ALLOWED_TRANSITIONS,
    can_transition,
    is_closed,
    is_open,
    next_statuses,
    requires_note,
)

STATUSES = list(RequestStatus.values)


def test_defines_moves_for_every_status_and_only_to_real_statuses() -> None:
    assert sorted(ALLOWED_TRANSITIONS) == sorted(STATUSES)
    for targets in ALLOWED_TRANSITIONS.values():
        assert set(targets) <= set(STATUSES)


@pytest.mark.parametrize("status", STATUSES)
def test_never_allows_a_status_to_move_to_itself(status: str) -> None:
    assert not can_transition(status, status)


def test_closed_is_terminal() -> None:
    assert next_statuses("closed") == ()
    assert is_closed("closed")
    assert not any(is_closed(status) for status in STATUSES if status != "closed")


def test_cannot_skip_review() -> None:
    assert not can_transition("pending_review", "approved")
    assert can_transition("pending_review", "in_progress")
    assert can_transition("in_progress", "approved")


def test_the_whole_table_is_exactly_the_documented_one() -> None:
    assert dict(ALLOWED_TRANSITIONS) == {
        "pending_review": ("in_progress", "rejected"),
        "in_progress": ("needs_correction", "approved", "rejected"),
        "needs_correction": ("in_progress", "rejected"),
        "approved": ("closed",),
        "rejected": ("closed",),
        "closed": (),
    }


def test_every_status_can_eventually_reach_closed() -> None:
    def reaches_closed(start: str, seen: frozenset[str] = frozenset()) -> bool:
        if start == "closed":
            return True
        if start in seen:
            return False
        return any(reaches_closed(nxt, seen | {start}) for nxt in next_statuses(start))

    for status in STATUSES:
        assert reaches_closed(status), status


def test_exactly_the_three_working_statuses_are_open() -> None:
    assert sorted(status for status in STATUSES if is_open(status)) == [
        "in_progress",
        "needs_correction",
        "pending_review",
    ]


def test_a_reason_is_required_for_rejections_and_correction_requests_only() -> None:
    assert sorted(status for status in STATUSES if requires_note(status)) == [
        "needs_correction",
        "rejected",
    ]
