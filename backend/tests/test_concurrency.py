"""Real row-lock behaviour: several threads, each with its own database connection.

These tests commit for real (``transaction=True``), so they are slower than the rest and carry the
``concurrency`` marker (``pytest -m "not concurrency"`` skips them).
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

import pytest
from django.db import connections
from django.utils import timezone

from apps.requests.models import ServiceRequest, TimelineEvent
from apps.requests.workflow import OPEN_STATUSES
from apps.users.models import AccessToken, User
from tests.helpers import (
    DEMO_PASSWORD,
    REQ,
    Api,
    Reply,
    customer_api,
    staff_api,
    uid,
    valid_loan,
    with_check_digit,
)

pytestmark = [
    pytest.mark.concurrency,
    pytest.mark.django_db(transaction=True),
    pytest.mark.usefixtures("demo"),
]

TIMEOUT = 90


def in_parallel(*jobs: Callable[[], Any]) -> list[Any]:
    """Start every job at the same moment, each on its own thread (and connection)."""
    barrier = threading.Barrier(len(jobs))

    def run(job: Callable[[], Any]) -> Any:
        try:
            barrier.wait(timeout=30)
            return job()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = [pool.submit(run, job) for job in jobs]
        return [future.result(timeout=TIMEOUT) for future in futures]


def sequences_of(request_id: str) -> list[int]:
    return list(
        TimelineEvent.objects.filter(request__id=request_id)
        .order_by("sequence")
        .values_list("sequence", flat=True)
    )


def statuses(replies: list[Reply]) -> Counter[int]:
    return Counter(reply.status for reply in replies)


class TestSerialisedWritesToOneRequest:
    def test_two_simultaneous_status_changes_one_wins_and_the_other_is_refused(self) -> None:
        admin, reza = staff_api("admin"), staff_api("reza")
        replies = in_parallel(
            lambda: Api(admin.token).transition(REQ.loan_pending, "in_progress"),
            lambda: Api(reza.token).transition(REQ.loan_pending, "in_progress"),
        )
        assert statuses(replies) == {200: 1, 409: 1}
        loser = next(reply for reply in replies if reply.status == 409)
        assert loser.code == "invalid_transition"

        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "in_progress"
        changes = TimelineEvent.objects.filter(
            request__id=REQ.loan_pending, kind="status_changed"
        ).count()
        assert changes == 1
        events = sequences_of(REQ.loan_pending)
        assert events == list(range(len(events)))

    def test_many_simultaneous_messages_get_unique_gapless_sequence_numbers(self) -> None:
        amir = customer_api("amir")
        before = len(sequences_of(REQ.loan_in_progress))
        count = 12
        replies = in_parallel(
            *[
                (lambda n=n: Api(amir.token).message(REQ.loan_in_progress, f"message {n}"))
                for n in range(count)
            ]
        )
        assert statuses(replies) == {201: count}
        sequences = sequences_of(REQ.loan_in_progress)
        assert sequences == list(range(before + count))
        bodies = set(
            TimelineEvent.objects.filter(request__id=REQ.loan_in_progress, kind="message")
            .exclude(body__startswith="مدارک")
            .values_list("body", flat=True)
        )
        assert {f"message {n}" for n in range(count)} <= bodies

    def test_mixed_writers_on_one_request_keep_the_timeline_consistent(self) -> None:
        amir, reza, admin = customer_api("amir"), staff_api("reza"), staff_api("admin")
        replies = in_parallel(
            lambda: Api(amir.token).message(REQ.loan_in_progress, "from the applicant"),
            lambda: Api(reza.token).message(REQ.loan_in_progress, "internal", "internal"),
            lambda: Api(reza.token).assign(REQ.loan_in_progress, None),
            lambda: Api(admin.token).assign(REQ.loan_in_progress, uid("u-reza")),
            lambda: Api(admin.token).transition(REQ.loan_in_progress, "approved", "done"),
            lambda: Api(reza.token).message(REQ.loan_in_progress, "another", "public"),
        )
        assert all(reply.status in (200, 201, 409) for reply in replies), statuses(replies)
        sequences = sequences_of(REQ.loan_in_progress)
        assert sequences == list(range(len(sequences)))
        request = ServiceRequest.objects.get(pk=REQ.loan_in_progress)
        last = TimelineEvent.objects.filter(request_id=request.pk).order_by("-sequence").first()
        assert last is not None
        assert request.updated_at == last.at

    def test_the_slower_of_two_closers_is_told_the_request_is_closed(self) -> None:
        ServiceRequest.objects.filter(pk=REQ.housing_approved).update(status="approved")
        admin, maryam = staff_api("admin"), staff_api("maryam")
        replies = in_parallel(
            lambda: Api(admin.token).transition(REQ.housing_approved, "closed"),
            lambda: Api(maryam.token).transition(REQ.housing_approved, "closed"),
        )
        assert statuses(replies) == {200: 1, 409: 1}
        assert next(r for r in replies if r.status == 409).code == "request_closed"


class TestAccountChangesRaceWithWork:
    def test_a_claim_racing_a_deactivation_never_leaves_open_work_with_an_inactive_assignee(
        self,
    ) -> None:
        for _ in range(8):
            ServiceRequest.objects.filter(pk=REQ.loan_pending).update(
                assignee=None, status="pending_review"
            )
            User.objects.filter(pk=uid("u-reza")).update(is_active=True)
            AccessToken.objects.all().delete()
            admin, reza = staff_api("admin"), staff_api("reza")

            claim, deactivate = in_parallel(
                partial(Api(reza.token).transition, REQ.loan_pending, "in_progress"),
                partial(
                    Api(admin.token).patch,
                    f"/api/staff/{uid('u-reza')}/",
                    {"departmentIds": ["loan"], "isActive": False},
                ),
            )
            assert deactivate.status == 200
            assert claim.status in (200, 401), claim

            stranded = ServiceRequest.objects.filter(
                assignee__is_active=False, status__in=OPEN_STATUSES
            )
            assert not stranded.exists()
            assert not AccessToken.objects.filter(
                user_id=uid("u-reza"), revoked_at__isnull=True
            ).exists()
            sequences = sequences_of(REQ.loan_pending)
            assert sequences == list(range(len(sequences)))

    def test_an_assignment_racing_a_department_change_never_strands_work(self) -> None:
        for _ in range(8):
            ServiceRequest.objects.filter(pk=REQ.loan_pending).update(
                assignee=None, status="pending_review"
            )
            User.objects.filter(pk=uid("u-reza")).update(department_ids=["loan"], is_active=True)
            AccessToken.objects.all().delete()
            admin, reza = staff_api("admin"), staff_api("reza")

            in_parallel(
                partial(Api(reza.token).assign, REQ.loan_pending, str(uid("u-reza"))),
                partial(
                    Api(admin.token).patch,
                    f"/api/staff/{uid('u-reza')}/",
                    {"departmentIds": ["housing"], "isActive": True},
                ),
            )
            request = ServiceRequest.objects.get(pk=REQ.loan_pending)
            if request.assignee_id is not None:
                assignee = User.objects.get(pk=request.assignee_id)
                assert request.department in assignee.department_ids, "stranded"

    def test_signing_in_while_being_deactivated_leaves_no_live_session(self) -> None:
        for _ in range(8):
            User.objects.filter(pk=uid("u-sara")).update(is_active=True)
            AccessToken.objects.all().delete()
            admin = staff_api("admin")
            login, deactivate = in_parallel(
                partial(
                    Api().post,
                    "/api/auth/login/staff/",
                    {"username": "sara", "password": DEMO_PASSWORD},
                ),
                partial(
                    Api(admin.token).patch,
                    f"/api/staff/{uid('u-sara')}/",
                    {"departmentIds": ["raw_material"], "isActive": False},
                ),
            )
            assert deactivate.status == 200
            assert login.status in (200, 401)
            live = AccessToken.objects.filter(
                user_id=uid("u-sara"), revoked_at__isnull=True, expires_at__gt=timezone.now()
            )
            assert not live.exists()

    def test_filing_while_a_service_is_paused_is_either_before_or_refused(self) -> None:
        admin, amir = staff_api("admin"), customer_api("amir")
        before = ServiceRequest.objects.count()
        pause, *filings = in_parallel(
            lambda: Api(admin.token).patch(
                "/api/catalog/services/personal-loan/active/", {"isActive": False}
            ),
            *[lambda: Api(amir.token).create(valid_loan) for _ in range(6)],
        )
        assert pause.status == 200
        assert all(reply.status in (201, 409) for reply in filings), statuses(filings)
        created = sum(1 for reply in filings if reply.status == 201)
        assert ServiceRequest.objects.count() == before + created
        # Once the pause has committed, nothing more is accepted.
        assert Api(amir.token).create(valid_loan).status == 409


class TestUniqueness:
    def test_simultaneous_filings_get_distinct_tracking_codes(self) -> None:
        amir = customer_api("amir")
        before = ServiceRequest.objects.count()
        replies = in_parallel(*[lambda: Api(amir.token).create(valid_loan) for _ in range(10)])
        assert statuses(replies) == {201: 10}
        assert len({reply.data["trackingCode"] for reply in replies}) == 10
        assert ServiceRequest.objects.count() == before + 10
        for reply in replies:
            assert sequences_of(reply.data["id"]) == [0]

    def test_simultaneous_registrations_of_one_national_id_create_exactly_one_account(self) -> None:
        national_id = with_check_digit("123456780")

        def register(n: int) -> Reply:
            return Api().post(
                "/api/auth/register/",
                {
                    "fullName": "Nima Ahmadi",
                    "nationalId": national_id,
                    "phone": f"0915111220{n}",
                    "postalCode": "1234567890",
                    "address": "Mashhad, Sajjad Blvd, No. 4",
                    "password": "Strong1pass",
                },
            )

        before = User.objects.count()
        replies = in_parallel(*[lambda n=n: register(n) for n in range(5)])
        assert statuses(replies) == {201: 1, 409: 4}
        assert {reply.code for reply in replies if reply.status == 409} == {"national_id_taken"}
        assert User.objects.count() == before + 1

    def test_simultaneous_registrations_of_one_phone_create_exactly_one_account(self) -> None:
        def register(n: int) -> Reply:
            return Api().post(
                "/api/auth/register/",
                {
                    "fullName": "Nima Ahmadi",
                    "nationalId": with_check_digit(f"23456789{n}"),
                    "phone": "09151112233",
                    "postalCode": "1234567890",
                    "address": "Mashhad, Sajjad Blvd, No. 4",
                    "password": "Strong1pass",
                },
            )

        replies = in_parallel(*[lambda n=n: register(n) for n in range(5)])
        assert statuses(replies) == {201: 1, 409: 4}
        assert {reply.code for reply in replies if reply.status == 409} == {"phone_taken"}

    def test_simultaneous_creation_of_one_username_creates_exactly_one_account(self) -> None:
        admin = staff_api("admin")
        body = {
            "nameFa": "نیما",
            "nameEn": "Nima",
            "username": "nima",
            "password": "Welcome1pass",
            "departmentIds": ["loan"],
        }
        replies = in_parallel(
            *[lambda: Api(admin.token).post("/api/staff/", body) for _ in range(4)]
        )
        assert statuses(replies) == {201: 1, 409: 3}
        assert {reply.code for reply in replies if reply.status == 409} == {"username_taken"}
        assert User.objects.filter(username="nima").count() == 1


class TestDemoResetAmongWriters:
    def test_a_reset_in_the_middle_of_other_writes_neither_deadlocks_nor_corrupts(self) -> None:
        admin = staff_api("admin")
        amir, reza, sara = customer_api("amir"), staff_api("reza"), staff_api("sara")

        def writer(client: Api, request_id: str, visibility: str) -> list[Reply]:
            return [
                Api(client.token).message(request_id, f"note {n}", visibility) for n in range(4)
            ]

        def resetter() -> list[Reply]:
            return [Api(admin.token).post("/api/demo/reset/") for _ in range(2)]

        results = in_parallel(
            lambda: writer(amir, REQ.loan_in_progress, "public"),
            lambda: writer(reza, REQ.loan_in_progress, "internal"),
            lambda: writer(sara, REQ.raw_needs_correction, "public"),
            lambda: [Api(admin.token).assign(REQ.loan_pending, None) for _ in range(3)],
            resetter,
        )
        replies = [reply for group in results for reply in group]
        assert all(reply.status != 500 for reply in replies), statuses(replies)
        assert all(reply.status in (200, 201, 204, 401, 404) for reply in replies), statuses(
            replies
        )
        assert all(reply.status == 204 for reply in results[-1])

        # Whatever interleaving happened, the end state is a coherent database.
        assert ServiceRequest.objects.count() == 8
        for request_id in ServiceRequest.objects.values_list("pk", flat=True):
            sequences = sequences_of(str(request_id))
            assert sequences == list(range(len(sequences)))
        assert User.objects.count() == 8
