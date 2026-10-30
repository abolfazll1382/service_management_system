"""The audit trail endpoint."""

from __future__ import annotations

import json
import re

import pytest

from apps.audit.models import AuditLog
from apps.users.models import User
from tests.helpers import REQ, Api, customer_api, expect_error, staff_api, uid

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]

NEW_STAFF = {
    "nameFa": "نیما",
    "nameEn": "Nima",
    "username": "nima",
    "password": "Welcome1pass",
    "departmentIds": ["loan"],
}


class TestAuditLog:
    def test_records_who_did_what_newest_first_and_pages(self) -> None:
        admin = staff_api("admin")
        admin.patch("/api/catalog/services/steel-supply/active/", {"isActive": False})
        admin.post("/api/staff/", NEW_STAFF)

        page = admin.audit().data
        assert [entry["action"] for entry in page["items"]][:3] == [
            "staff_created",
            "service_paused",
            "auth_login",
        ]
        assert page["items"][0]["target"] == "nima"
        assert page["items"][0]["actor"]["id"] == uid("u-admin")
        assert page["items"][1]["target"] == "steel-supply"

        small = admin.audit(pageSize=2, page=2).data
        assert (small["total"], small["page"], small["pageSize"]) == (page["total"], 2, 2)
        assert len(small["items"]) == min(2, page["total"] - 2)
        assert small["items"][0]["id"] != page["items"][0]["id"]

    def test_entries_have_exactly_the_documented_shape(self) -> None:
        admin = staff_api("admin")
        admin.post("/api/staff/", NEW_STAFF)
        created, login = admin.audit().data["items"][:2]
        assert set(created) == {"id", "at", "actor", "action", "target"}
        assert re.fullmatch(r"[0-9]+", created["id"])
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", created["at"])
        assert created["actor"] == {
            "id": uid("u-admin"),
            "role": "admin",
            "name": {"fa": "مدیر سامانه", "en": "System Administrator"},
        }
        # An entry without a target leaves the key out (the frontend's optional ``target?``).
        assert login["action"] == "auth_login"
        assert "target" not in login

    def test_the_page_envelope_and_defaults(self) -> None:
        page = staff_api("admin").audit().data
        assert set(page) == {"items", "total", "page", "pageSize"}
        assert (page["page"], page["pageSize"]) == (1, 15)

    def test_ids_increase_so_newest_first_is_a_strict_order(self) -> None:
        admin = staff_api("admin")
        for _ in range(3):
            admin.patch("/api/catalog/services/steel-supply/active/", {"isActive": False})
        ids = [int(entry["id"]) for entry in admin.audit(pageSize=100).data["items"]]
        assert ids == sorted(ids, reverse=True)
        assert len(set(ids)) == len(ids)

    def test_failed_sign_ins_have_no_actor(self) -> None:
        Api().post("/api/auth/login/staff/", {"username": "reza", "password": "wrong-pass1"})
        items = staff_api("admin").audit().data["items"]
        failed = next(entry for entry in items if entry["action"] == "auth_login_failed")
        assert failed["actor"] is None
        assert failed["target"] == "reza"

    def test_captures_request_activity_without_copying_message_text_or_personal_details(
        self,
    ) -> None:
        customer_api("amir").message(REQ.loan_in_progress, "My secret message body")
        items = staff_api("admin").audit().data["items"]
        assert any(entry["action"] == "request_message_added" for entry in items)
        text = json.dumps(items, ensure_ascii=False)
        assert "My secret message body" not in text
        assert "0045813922" not in text
        assert "09121234567" not in text

    def test_every_kind_of_activity_leaves_an_entry(self) -> None:
        reza = staff_api("reza")
        reza.assign(REQ.loan_pending, uid("u-reza"))
        reza.transition(REQ.loan_pending, "in_progress")
        reza.message(REQ.loan_pending, "hello", "public")
        customer_api("amir").create(
            {
                "serviceId": "personal-loan",
                "description": "I need a loan to pay for wedding costs.",
                "details": {"amount": 100_000_000, "termMonths": "12", "purpose": "Wedding"},
            }
        )
        actions = {
            entry["action"] for entry in staff_api("admin").audit(pageSize=100).data["items"]
        }
        assert {
            "auth_login",
            "request_assigned",
            "request_status_changed",
            "request_message_added",
            "request_created",
        } <= actions

    def test_an_entry_outlives_the_account_that_made_it(self) -> None:
        admin = staff_api("admin")
        admin.post("/api/staff/", NEW_STAFF)
        staff_api("nima", "Welcome1pass")
        User.objects.filter(username="nima").delete()
        entry = next(
            item
            for item in admin.audit(pageSize=100).data["items"]
            if item["action"] == "auth_login" and item["actor"]["name"]["en"] == "Nima"
        )
        assert entry["actor"]["id"] == "00000000-0000-0000-0000-000000000000"
        assert entry["actor"]["role"] == "staff"

    def test_hostile_targets_are_cleaned_before_they_are_stored(self) -> None:
        from apps.audit.choices import AuditAction
        from apps.audit.services import AuditService

        entry = AuditService.record(
            actor=None, action=AuditAction.AUTH_LOGIN_FAILED, target="a\nb\x00c\x1b[31m" + "x" * 100
        )
        assert not set(entry.target) & {"\n", "\x00", "\x1b"}
        assert len(entry.target) <= 64

    @pytest.mark.parametrize(
        ("params", "field"),
        [({"page": 0}, "page"), ({"pageSize": 101}, "pageSize"), ({"pageSize": 0}, "pageSize")],
    )
    def test_bad_paging_is_a_validation_error(self, params: dict[str, int], field: str) -> None:
        reply = staff_api("admin").audit(**params)
        expect_error(reply, "validation")
        assert list(reply.data["errors"]) == [field]

    def test_a_page_past_the_end_is_empty(self) -> None:
        reply = staff_api("admin").audit(page=50)
        assert reply.data["items"] == []
        assert reply.data["total"] == AuditLog.objects.count()

    def test_is_admin_only(self) -> None:
        expect_error(Api().audit(), "unauthenticated")
        expect_error(staff_api("reza").audit(), "forbidden")
        expect_error(customer_api("amir").audit(), "forbidden")
