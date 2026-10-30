"""``POST /api/demo/reset/``."""

from __future__ import annotations

import pytest
from django.contrib.auth.hashers import check_password
from django.test import override_settings

from apps.audit.models import AuditLog
from apps.catalog.models import Service
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.users.models import AccessToken, User
from tests.helpers import (
    DEMO_PASSWORD,
    NATIONAL_IDS,
    REQ,
    Api,
    customer_api,
    expect_error,
    staff_api,
    uid,
    valid_loan,
    with_check_digit,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]


class TestDemoReset:
    def test_restores_the_seed_ends_other_sessions_but_keeps_the_administrator_signed_in(
        self,
    ) -> None:
        amir = customer_api("amir")
        created = amir.create(valid_loan).data
        admin = staff_api("admin")
        assert ServiceRequest.objects.filter(pk=created["id"]).exists()

        reply = admin.post("/api/demo/reset/")
        assert reply.status == 204
        assert reply.data is None

        assert ServiceRequest.objects.count() == 8
        assert not ServiceRequest.objects.filter(pk=created["id"]).exists()
        assert admin.me().data["username"] == "admin"
        assert [entry["action"] for entry in admin.audit().data["items"]] == ["demo_reset"]
        expect_error(amir.me(), "unauthenticated")
        assert AccessToken.objects.count() == 1

    def test_the_audit_entry_names_the_administrator_who_did_it(self) -> None:
        staff_api("admin").post("/api/demo/reset/")
        entry = AuditLog.objects.get()
        assert entry.action == "demo_reset"
        assert str(entry.actor_id) == uid("u-admin")
        assert entry.actor_role == "admin"

    def test_puts_everything_back_as_it_was(self) -> None:
        admin = staff_api("admin")
        reza = staff_api("reza")
        reza.transition(REQ.loan_pending, "in_progress")
        reza.message(REQ.loan_in_progress, "extra", "public")
        admin.patch("/api/catalog/services/personal-loan/active/", {"isActive": False})
        admin.patch(f"/api/staff/{uid('u-sara')}/", {"departmentIds": ["loan"], "isActive": False})
        User.objects.filter(pk=uid("u-ali")).update(password="x")

        admin.post("/api/demo/reset/")

        assert ServiceRequest.objects.get(pk=REQ.loan_pending).status == "pending_review"
        assert ServiceRequest.objects.get(pk=REQ.loan_pending).assignee_id is None
        assert TimelineEvent.objects.filter(request__id=REQ.loan_in_progress).count() == 4
        assert Service.objects.get(pk="personal-loan").is_active is True
        sara = User.objects.get(pk=uid("u-sara"))
        assert sara.is_active is True
        assert sara.department_ids == ["raw_material"]
        assert check_password(DEMO_PASSWORD, User.objects.get(pk=uid("u-ali")).password)
        assert TimelineEvent.objects.count() == 29

    def test_removes_accounts_that_are_not_part_of_the_seed_but_keeps_other_administrators(
        self,
    ) -> None:
        admin = staff_api("admin")
        admin.post(
            "/api/staff/",
            {
                "nameFa": "نیما",
                "nameEn": "Nima",
                "username": "nima",
                "password": "Welcome1pass",
                "departmentIds": ["loan"],
            },
        )
        Api().post(
            "/api/auth/register/",
            {
                "fullName": "Nima Ahmadi",
                "nationalId": with_check_digit("123456789"),
                "phone": "09151112233",
                "postalCode": "1234567890",
                "address": "Mashhad, Sajjad Blvd, No. 4",
                "password": "Strong1pass",
            },
        )
        second_admin = User.objects.create(
            role="admin", username="root", name_fa="مدیر", name_en="Root", password="x"
        )

        admin.post("/api/demo/reset/")

        assert not User.objects.filter(username="nima").exists()
        assert not User.objects.filter(national_id=with_check_digit("123456789")).exists()
        assert User.objects.filter(pk=second_admin.pk).exists()
        assert User.objects.count() == 9

    def test_is_repeatable(self) -> None:
        admin = staff_api("admin")
        assert admin.post("/api/demo/reset/").status == 204
        assert admin.post("/api/demo/reset/").status == 204
        assert ServiceRequest.objects.count() == 8
        assert [entry["action"] for entry in admin.audit().data["items"]] == ["demo_reset"]

    def test_seed_accounts_can_sign_in_again_afterwards(self) -> None:
        staff_api("admin").post("/api/demo/reset/")
        assert staff_api("reza").me().data["username"] == "reza"
        assert customer_api("hossein").me().data["nationalId"] == NATIONAL_IDS["hossein"]

    def test_is_for_administrators_only(self) -> None:
        expect_error(Api().post("/api/demo/reset/"), "unauthenticated")
        expect_error(staff_api("reza").post("/api/demo/reset/"), "forbidden")
        expect_error(customer_api("amir").post("/api/demo/reset/"), "forbidden")
        assert ServiceRequest.objects.count() == 8

    @override_settings(ENABLE_DEMO_RESET=False)
    def test_does_not_exist_where_the_demo_tooling_is_off(self) -> None:
        admin = staff_api("admin")
        for client in (Api(), staff_api("reza"), admin):
            expect_error(client.post("/api/demo/reset/"), "not_found")
        assert AuditLog.objects.filter(action="demo_reset").count() == 0

    def test_a_deactivated_administrators_token_cannot_reset(self) -> None:
        admin = staff_api("admin")
        User.objects.filter(pk=uid("u-admin")).update(is_active=False)
        expect_error(admin.post("/api/demo/reset/"), "unauthenticated")
