"""Processing a request: transitions, the correction loop, messages, assignment
(port of the frontend's ``api.workflow.test.ts``)."""

from __future__ import annotations

from typing import Any

import pytest

from apps.audit.models import AuditLog
from apps.requests.models import ServiceRequest, TimelineEvent
from tests.helpers import (
    REQ,
    Api,
    customer_api,
    expect_error,
    staff_api,
    uid,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]


def kinds(request: dict[str, Any]) -> list[str]:
    return [event["kind"] for event in request["timeline"]]


def audit_actions() -> list[str]:
    return list(AuditLog.objects.order_by("id").values_list("action", flat=True))


def assert_consistent(request: dict[str, Any]) -> None:
    """A rendered request agrees with itself: ``updatedAt`` is its last event, and the stored
    sequence numbers are 0..n-1 without gaps or repeats."""
    assert request["updatedAt"] == request["timeline"][-1]["at"]
    sequences = list(
        TimelineEvent.objects.filter(request_id=request["id"])
        .order_by("sequence")
        .values_list("sequence", flat=True)
    )
    assert sequences == list(range(len(sequences)))


class TestProcessingARequest:
    def test_starting_a_review_moves_it_to_in_progress_and_claims_it_for_the_staff_member(
        self,
    ) -> None:
        reza = staff_api("reza")
        before = len(reza.request(REQ.loan_pending).data["timeline"])
        reply = reza.transition(REQ.loan_pending, "in_progress")
        assert reply.status == 200
        updated = reply.data

        assert updated["status"] == "in_progress"
        assert updated["assignee"] == {
            "id": uid("u-reza"),
            "role": "staff",
            "name": {"fa": "رضا کریمی", "en": "Reza Karimi"},
        }
        assert kinds(updated)[before:] == ["assigned", "status_changed"]
        change = updated["timeline"][-1]
        assert change["from"] == "pending_review"
        assert change["to"] == "in_progress"
        assert change["actor"]["id"] == uid("u-reza")
        assert change["actor"]["role"] == "staff"
        assert_consistent(updated)

    def test_an_administrator_starting_a_review_does_not_claim_it(self) -> None:
        updated = staff_api("admin").transition(REQ.loan_pending, "in_progress").data
        assert updated["assignee"] is None
        assert kinds(updated)[-1] == "status_changed"
        assert "assigned" not in kinds(updated)[1:]

    def test_an_already_assigned_request_keeps_its_assignee(self) -> None:
        # Pending but assigned to Reza: give it to him first, then another actor starts the review.
        ServiceRequest.objects.filter(pk=REQ.loan_pending).update(assignee_id=uid("u-reza"))
        updated = staff_api("admin").transition(REQ.loan_pending, "in_progress").data
        assert updated["assignee"]["id"] == uid("u-reza")

    def test_walks_the_happy_path_and_refuses_to_skip_review(self) -> None:
        reza = staff_api("reza")
        expect_error(reza.transition(REQ.loan_pending, "approved"), "invalid_transition")
        assert reza.transition(REQ.loan_pending, "in_progress").status == 200
        approved = reza.transition(REQ.loan_pending, "approved", "Approved for 24 months.")
        assert approved.status == 200
        closed = reza.transition(REQ.loan_pending, "closed")
        assert closed.data["status"] == "closed"
        expect_error(reza.transition(REQ.loan_pending, "in_progress"), "request_closed")
        assert_consistent(closed.data)

    @pytest.mark.parametrize(
        ("start", "target"),
        [
            ("pending_review", "pending_review"),
            ("pending_review", "approved"),
            ("pending_review", "needs_correction"),
            ("pending_review", "closed"),
            ("in_progress", "pending_review"),
            ("in_progress", "in_progress"),
            ("in_progress", "closed"),
            ("needs_correction", "approved"),
            ("needs_correction", "closed"),
            ("approved", "in_progress"),
            ("approved", "rejected"),
            ("rejected", "in_progress"),
            ("rejected", "approved"),
        ],
    )
    def test_every_illegal_move_is_refused_and_changes_nothing(
        self, start: str, target: str
    ) -> None:
        ServiceRequest.objects.filter(pk=REQ.loan_pending).update(status=start)
        admin = staff_api("admin")  # signing in is itself audited: count afterwards
        events = TimelineEvent.objects.count()
        audits = AuditLog.objects.count()
        reply = admin.transition(REQ.loan_pending, target, "because")
        expect_error(reply, "invalid_transition")
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == start
        assert (TimelineEvent.objects.count(), AuditLog.objects.count()) == (events, audits)

    @pytest.mark.parametrize(
        ("start", "target"),
        [
            ("pending_review", "in_progress"),
            ("pending_review", "rejected"),
            ("in_progress", "needs_correction"),
            ("in_progress", "approved"),
            ("in_progress", "rejected"),
            ("needs_correction", "in_progress"),
            ("needs_correction", "rejected"),
            ("approved", "closed"),
            ("rejected", "closed"),
        ],
    )
    def test_every_legal_move_is_accepted(self, start: str, target: str) -> None:
        ServiceRequest.objects.filter(pk=REQ.loan_pending).update(status=start)
        reply = staff_api("admin").transition(REQ.loan_pending, target, "ok")
        assert reply.status == 200
        assert reply.data["status"] == target

    def test_requires_a_reason_to_reject_or_ask_for_corrections_and_shows_it_to_the_applicant(
        self,
    ) -> None:
        reza = staff_api("reza")
        for note in (None, "", "   "):
            reply = reza.transition(REQ.loan_pending, "rejected", note)
            expect_error(reply, "validation")
            assert reply.data["errors"] == {"note": ["validation.note.required"]}
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "pending_review"

        assert (
            reza.transition(REQ.loan_pending, "rejected", "Income documents are missing.").status
            == 200
        )
        seen = customer_api("hossein").request(REQ.loan_pending).data
        assert seen["status"] == "rejected"
        assert seen["timeline"][-1] == {
            "id": seen["timeline"][-1]["id"],
            "at": seen["timeline"][-1]["at"],
            "actor": seen["timeline"][-1]["actor"],
            "kind": "message",
            "visibility": "public",
            "body": "Income documents are missing.",
        }
        assert seen["timeline"][-2]["kind"] == "status_changed"

    def test_correction_requests_need_a_reason_too(self) -> None:
        reza = staff_api("reza")
        reza.transition(REQ.loan_pending, "in_progress")
        expect_error(reza.transition(REQ.loan_pending, "needs_correction"), "validation")
        ok = reza.transition(REQ.loan_pending, "needs_correction", "Please attach your payslip.")
        assert ok.data["status"] == "needs_correction"

    def test_a_note_on_an_ordinary_move_is_recorded_as_a_public_message_after_the_change(
        self,
    ) -> None:
        reza = staff_api("reza")
        reza.transition(REQ.loan_pending, "in_progress")
        updated = reza.transition(REQ.loan_pending, "approved", "Approved for 24 months.").data
        assert kinds(updated)[-2:] == ["status_changed", "message"]
        assert updated["timeline"][-1]["body"] == "Approved for 24 months."
        assert updated["timeline"][-1]["visibility"] == "public"

    def test_a_blank_note_on_an_ordinary_move_is_not_recorded(self) -> None:
        reza = staff_api("reza")
        reza.transition(REQ.loan_pending, "in_progress")
        updated = reza.transition(REQ.loan_pending, "approved", "   ").data
        assert kinds(updated)[-1] == "status_changed"

    def test_rejects_an_invalid_or_unknown_target_status(self) -> None:
        reza = staff_api("reza")
        reply = reza.transition(REQ.loan_pending, "teleported")
        expect_error(reply, "validation")
        assert reply.data["errors"] == {"to": ["validation.invalid"]}
        expect_error(reza.post(f"/api/requests/{REQ.loan_pending}/transition/", {}), "validation")
        expect_error(
            reza.post(f"/api/requests/{REQ.loan_pending}/transition/", {"to": ["approved"]}),
            "validation",
        )
        expect_error(reza.transition("req-nope", "in_progress"), "not_found")
        expect_error(
            reza.transition("00000000-0000-0000-0000-000000000000", "in_progress"), "not_found"
        )

    def test_an_overlong_note_is_refused(self) -> None:
        reply = staff_api("reza").transition(REQ.loan_pending, "in_progress", "x" * 1001)
        expect_error(reply, "validation")
        assert list(reply.data["errors"]) == ["note"]

    def test_each_change_is_audited_with_the_tracking_code(self) -> None:
        reza = staff_api("reza")
        reza.transition(REQ.loan_pending, "in_progress")
        entry = AuditLog.objects.filter(action="request_status_changed").get()
        assert entry.target == ServiceRequest.objects.get(pk=REQ.loan_pending).tracking_code
        assert str(entry.actor_id) == uid("u-reza")

    def test_updated_at_moves_with_every_change(self) -> None:
        reza = staff_api("reza")
        before = reza.request(REQ.loan_pending).data["updatedAt"]
        after = reza.transition(REQ.loan_pending, "in_progress").data["updatedAt"]
        assert after > before


class TestClosedRequestsAreFrozen:
    def test_accept_no_status_change_assignment_or_message_from_anyone(self) -> None:
        sara, admin, hossein = staff_api("sara"), staff_api("admin"), customer_api("hossein")
        before = (TimelineEvent.objects.count(), AuditLog.objects.count())
        expect_error(sara.transition(REQ.raw_closed, "in_progress"), "request_closed")
        expect_error(sara.assign(REQ.raw_closed, uid("u-sara")), "request_closed")
        expect_error(sara.assign(REQ.raw_closed, None), "request_closed")
        expect_error(sara.message(REQ.raw_closed, "late", "public"), "request_closed")
        expect_error(sara.message(REQ.raw_closed, "late", "internal"), "request_closed")
        expect_error(admin.transition(REQ.raw_closed, "in_progress"), "request_closed")
        expect_error(hossein.message(REQ.raw_closed, "late", "public"), "request_closed")
        assert before == (TimelineEvent.objects.count(), AuditLog.objects.count())

    def test_a_closed_request_can_still_be_read(self) -> None:
        assert staff_api("sara").request(REQ.raw_closed).status == 200
        assert customer_api("hossein").request(REQ.raw_closed).data["status"] == "closed"


class TestMessagesAndTheCorrectionLoop:
    def test_an_applicants_reply_to_a_correction_request_hands_the_request_back_to_staff(
        self,
    ) -> None:
        maryam = customer_api("maryam")
        reply = maryam.message(REQ.raw_needs_correction, "The project number is 42.")
        assert reply.status == 201
        updated = reply.data
        assert updated["status"] == "in_progress"
        assert kinds(updated)[-2:] == ["message", "status_changed"]
        last = updated["timeline"][-1]
        assert last["actor"]["role"] == "customer"  # recorded as THEIR action
        assert (last["from"], last["to"]) == ("needs_correction", "in_progress")
        assert_consistent(updated)
        # ...without having gained the right to change statuses themselves:
        expect_error(maryam.transition(REQ.raw_needs_correction, "approved"), "forbidden")

    def test_an_internal_note_from_staff_on_a_correction_request_leaves_it_waiting(self) -> None:
        reply = staff_api("sara").message(REQ.raw_needs_correction, "waiting on them", "internal")
        assert reply.data["status"] == "needs_correction"

    def test_a_public_message_from_staff_on_a_correction_request_leaves_it_waiting(self) -> None:
        reply = staff_api("sara").message(REQ.raw_needs_correction, "any news?", "public")
        assert reply.data["status"] == "needs_correction"

    def test_a_reply_on_any_other_open_request_leaves_the_status_alone(self) -> None:
        reply = customer_api("amir").message(REQ.loan_in_progress, "Any news?")
        assert reply.status == 201
        assert reply.data["status"] == "in_progress"
        assert kinds(reply.data)[-1] == "message"

    def test_applicants_can_write_on_a_pending_or_approved_request(self) -> None:
        assert (
            customer_api("amir").message(REQ.vehicle_pending, "hello").data["status"]
            == "pending_review"
        )
        assert (
            customer_api("maryam").message(REQ.housing_approved, "thanks").data["status"]
            == "approved"
        )

    def test_a_message_records_the_author_and_the_visibility(self) -> None:
        reply = customer_api("amir").message(REQ.loan_in_progress, "  Any news?  ")
        message = reply.data["timeline"][-1]
        assert message["kind"] == "message"
        assert message["visibility"] == "public"
        assert message["body"] == "Any news?"  # surrounding whitespace is trimmed
        assert message["actor"]["id"] == uid("c-amir")
        assert message["actor"]["role"] == "customer"

    def test_validates_the_message_body_and_visibility(self) -> None:
        amir = customer_api("amir")
        empty = amir.message(REQ.loan_in_progress, "   ")
        expect_error(empty, "validation")
        assert empty.data["errors"] == {"body": ["validation.required"]}
        too_long = amir.message(REQ.loan_in_progress, "x" * 1001)
        expect_error(too_long, "validation")
        assert too_long.data["errors"] == {"body": ["validation.description.max"]}
        bad_visibility = amir.message(REQ.loan_in_progress, "ok", "secret")
        expect_error(bad_visibility, "validation")
        assert bad_visibility.data["errors"] == {"visibility": ["validation.invalid"]}
        missing = amir.post(f"/api/requests/{REQ.loan_in_progress}/messages/", {})
        assert set(missing.data["errors"]) == {"body", "visibility"}

    def test_the_length_limit_counts_characters_not_bytes(self) -> None:
        amir = customer_api("amir")
        assert amir.message(REQ.loan_in_progress, "x" * 1000).status == 201
        assert amir.message(REQ.loan_in_progress, "ن" * 1000).status == 201  # 2 bytes each
        assert amir.message(REQ.loan_in_progress, "😀" * 1000).status == 201  # 4 bytes each

    def test_text_the_database_cannot_store_is_a_validation_error_not_a_crash(self) -> None:
        amir = customer_api("amir")
        for body in ("nul\x00byte", "lone\ud800surrogate"):
            raw = b'{"visibility":"public","body":' + _json_string(body) + b"}"
            reply = amir.call("post", f"/api/requests/{REQ.loan_in_progress}/messages/", raw=raw)
            expect_error(reply, "validation")
            # Reported with the field's own key (a message body's is "required").
            assert reply.data["errors"] == {"body": ["validation.required"]}

    def test_messages_are_audited_without_their_text(self) -> None:
        customer_api("amir").message(REQ.loan_in_progress, "My secret message body")
        entry = AuditLog.objects.get(action="request_message_added")
        assert entry.target == ServiceRequest.objects.get(pk=REQ.loan_in_progress).tracking_code
        assert "secret" not in entry.target

    def test_a_message_moves_updated_at(self) -> None:
        amir = customer_api("amir")
        before = amir.request(REQ.loan_in_progress).data["updatedAt"]
        after = amir.message(REQ.loan_in_progress, "hi").data["updatedAt"]
        assert after > before


def _json_string(text: str) -> bytes:
    """``text`` as a JSON string literal, escaping everything non-ASCII (even lone surrogates)."""
    import json

    return json.dumps(text, ensure_ascii=True).encode("ascii")


class TestAssignment:
    def test_lets_staff_claim_a_request_in_their_department_and_release_it(self) -> None:
        reza = staff_api("reza")
        claimed = reza.assign(REQ.loan_pending, uid("u-reza"))
        assert claimed.status == 200
        assert claimed.data["assignee"]["id"] == uid("u-reza")
        last = claimed.data["timeline"][-1]
        assert last["kind"] == "assigned"
        assert last["assignee"]["id"] == uid("u-reza")
        assert last["actor"]["id"] == uid("u-reza")

        released = reza.assign(REQ.loan_pending, None)
        assert released.data["assignee"] is None
        assert released.data["timeline"][-1]["assignee"] is None
        assert_consistent(released.data)

    def test_adds_nothing_to_the_history_when_the_assignee_does_not_change(self) -> None:
        reza = staff_api("reza")
        before = reza.request(REQ.loan_in_progress).data
        audits = AuditLog.objects.count()
        again = reza.assign(REQ.loan_in_progress, uid("u-reza"))
        assert again.status == 200
        assert len(again.data["timeline"]) == len(before["timeline"])
        assert again.data["updatedAt"] == before["updatedAt"]
        assert AuditLog.objects.count() == audits

        # ...and releasing an unassigned request is just as quiet.
        reza.assign(REQ.loan_pending, None)
        assert AuditLog.objects.count() == audits

    def test_only_an_administrator_can_hand_work_to_a_colleague(self) -> None:
        admin = staff_api("admin")
        created = admin.post(
            "/api/staff/",
            {
                "nameFa": "نیما",
                "nameEn": "Nima",
                "username": "nima",
                "password": "Welcome1pass",
                "departmentIds": ["loan"],
            },
        )
        assert created.status == 201
        colleague = created.data["id"]

        reza = staff_api("reza")
        expect_error(reza.assign(REQ.loan_pending, colleague), "forbidden")
        assert [actor["id"] for actor in reza.assignable("loan").data] == [uid("u-reza")]

        handed = admin.assign(REQ.loan_pending, colleague)
        assert handed.data["assignee"]["id"] == colleague
        assert handed.data["timeline"][-1]["actor"]["role"] == "admin"
        assert sorted(actor["id"] for actor in admin.assignable("loan").data) == sorted(
            [uid("u-reza"), colleague]
        )

    def test_a_colleague_may_release_someone_elses_work_in_their_department(self) -> None:
        admin = staff_api("admin")
        nima = admin.post(
            "/api/staff/",
            {
                "nameFa": "نیما",
                "nameEn": "Nima",
                "username": "nima",
                "password": "Welcome1pass",
                "departmentIds": ["loan"],
            },
        ).data
        assert nima["username"] == "nima"
        released = staff_api("nima", "Welcome1pass").assign(REQ.loan_in_progress, None)
        assert released.data["assignee"] is None
        assert released.data["timeline"][-1]["actor"]["name"]["en"] == "Nima"

    def test_never_assigns_outside_the_assignees_department_or_to_a_non_staff_account(self) -> None:
        admin = staff_api("admin")
        expect_error(admin.assign(REQ.loan_pending, uid("u-sara")), "forbidden")  # raw materials
        expect_error(admin.assign(REQ.loan_pending, uid("c-amir")), "forbidden")  # a customer
        expect_error(admin.assign(REQ.loan_pending, uid("u-admin")), "forbidden")  # not staff
        expect_error(admin.assign(REQ.loan_pending, "no-such-user"), "not_found")
        expect_error(
            admin.assign(REQ.loan_pending, "00000000-0000-0000-0000-000000000000"), "not_found"
        )
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).assignee_id is None

    def test_a_deactivated_member_cannot_be_assigned_work(self) -> None:
        admin = staff_api("admin")
        admin.patch(f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["loan"], "isActive": False})
        expect_error(admin.assign(REQ.loan_pending, uid("u-reza")), "forbidden")
        assert admin.assignable("loan").data == []

    def test_staff_cannot_claim_for_someone_else_even_in_their_own_department(self) -> None:
        admin = staff_api("admin")
        created = admin.post(
            "/api/staff/",
            {
                "nameFa": "نیما",
                "nameEn": "Nima",
                "username": "nima",
                "password": "Welcome1pass",
                "departmentIds": ["loan"],
            },
        ).data
        expect_error(
            staff_api("nima", "Welcome1pass").assign(REQ.loan_pending, uid("u-reza")), "forbidden"
        )
        assert created["departmentIds"] == ["loan"]

    def test_the_assignee_id_is_mandatory_and_must_be_text_or_null(self) -> None:
        reza = staff_api("reza")
        url = f"/api/requests/{REQ.loan_pending}/assign/"
        for body in (
            {},
            {"assigneeId": 5},
            {"assigneeId": ""},
            {"assigneeId": ["x"]},
            {"assigneeId": "x" * 65},
        ):
            expect_error(reza.post(url, body), "validation")

    def test_the_assignable_list_needs_a_known_department(self) -> None:
        admin = staff_api("admin")
        expect_error(admin.get("/api/requests/assignable-staff/"), "validation")
        expect_error(admin.assignable("space_travel"), "validation")
        assert [a["id"] for a in admin.assignable("vehicle").data] == [uid("u-ali")]

    def test_assignment_is_audited(self) -> None:
        staff_api("reza").assign(REQ.loan_pending, uid("u-reza"))
        entry = AuditLog.objects.get(action="request_assigned")
        assert entry.target == ServiceRequest.objects.get(pk=REQ.loan_pending).tracking_code

    def test_assignment_to_a_missing_request_is_not_found(self) -> None:
        expect_error(staff_api("admin").assign("nope", None), "not_found")


class TestAnAssigneeKeepsTheirNameAsItWas:
    def test_renaming_later_does_not_rewrite_history(self) -> None:
        reza = staff_api("reza")
        reza.assign(REQ.loan_pending, uid("u-reza"))
        from apps.users.models import User

        User.objects.filter(pk=uid("u-reza")).update(name_en="Reza K. Renamed")
        events = Api(reza.token).request(REQ.loan_pending).data["timeline"]
        assert events[-1]["assignee"]["name"]["en"] == "Reza Karimi"
        assert events[-1]["actor"]["name"]["en"] == "Reza Karimi"
