"""Filing requests, service availability and team management
(port of the frontend's ``api.admin.test.ts``)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.audit.models import AuditLog
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.users.models import AccessToken, User
from tests.helpers import (
    DEMO_PASSWORD,
    REQ,
    Api,
    customer_api,
    expect_error,
    staff_api,
    uid,
    valid_loan,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]

NEW_STAFF: dict[str, Any] = {
    "nameFa": "نیما احمدی",
    "nameEn": "Nima Ahmadi",
    "username": "nima",
    "password": "Welcome1pass",
    "departmentIds": ["vehicle"],
}


class TestSubmittingARequest:
    def test_files_it_under_the_services_department_with_a_unique_tracking_code(self) -> None:
        amir = customer_api("amir")
        reply = amir.create(valid_loan)
        assert reply.status == 201
        created = reply.data
        assert created["status"] == "pending_review"
        assert created["departmentId"] == "loan"
        assert created["serviceId"] == "personal-loan"
        assert created["assignee"] is None
        assert created["customerId"] == uid("c-amir")
        assert created["customer"] == {
            "fullName": "امیر حسینی",
            "nationalId": "0045813922",
            "phone": "09121234567",
        }
        assert created["details"] == valid_loan["details"]
        assert created["description"] == valid_loan["description"]
        assert len(created["trackingCode"]) == 10
        assert created["trackingCode"].isdigit()
        assert len(created["timeline"]) == 1
        first = created["timeline"][0]
        assert first["kind"] == "submitted"
        assert first["actor"]["id"] == uid("c-amir")
        assert first["actor"]["role"] == "customer"
        assert created["submittedAt"] == created["updatedAt"] == first["at"]

        second = amir.create(valid_loan).data
        assert second["trackingCode"] != created["trackingCode"]
        assert second["id"] != created["id"]

    def test_the_request_keeps_the_applicant_as_they_were_when_it_was_filed(self) -> None:
        created = customer_api("amir").create(valid_loan).data
        User.objects.filter(pk=uid("c-amir")).update(full_name="Renamed", phone="09990000000")
        again = staff_api("reza").request(created["id"]).data
        assert again["customer"]["fullName"] == "امیر حسینی"
        assert again["customer"]["phone"] == "09121234567"

    def test_lands_in_the_right_departments_queue_and_nobody_elses(self) -> None:
        created = customer_api("amir").create(valid_loan).data
        code = created["trackingCode"]
        assert staff_api("reza").queue(search=code).data["total"] == 1
        for other in ("sara", "ali", "maryam"):
            assert staff_api(other).queue(search=code).data["total"] == 0, other
        assert staff_api("admin").queue(search=code).data["total"] == 1

    def test_ignores_fields_the_client_has_no_business_setting(self) -> None:
        amir = customer_api("amir")
        created = amir.create(
            {
                **valid_loan,
                "customerId": uid("c-hossein"),
                "status": "approved",
                "assignee": {"id": uid("u-reza")},
                "assigneeId": uid("u-reza"),
                "departmentId": "vehicle",
                "trackingCode": "0000000001",
                "id": "00000000-0000-0000-0000-000000000001",
                "details": {**valid_loan["details"], "isPreApproved": "yes"},
            }
        ).data
        assert created["customerId"] == uid("c-amir")
        assert created["status"] == "pending_review"
        assert created["assignee"] is None
        assert created["departmentId"] == "loan"
        assert created["trackingCode"] != "0000000001"
        assert created["id"] != "00000000-0000-0000-0000-000000000001"
        assert "isPreApproved" not in created["details"]

    def test_revalidates_the_services_own_fields_on_the_server(self) -> None:
        amir = customer_api("amir")
        details = valid_loan["details"]

        low = amir.create({**valid_loan, "details": {**details, "amount": 5}})
        expect_error(low, "validation")
        assert low.data["errors"] == {"details.amount": ["validation.number.min"]}

        high = amir.create({**valid_loan, "details": {**details, "amount": 10**12}})
        assert high.data["errors"] == {"details.amount": ["validation.number.max"]}

        term = amir.create({**valid_loan, "details": {**details, "termMonths": "7"}})
        assert term.data["errors"] == {"details.termMonths": ["validation.select"]}

        missing = amir.create({**valid_loan, "details": {"amount": 100_000_000}})
        assert missing.data["errors"] == {
            "details.termMonths": ["validation.select"],
            "details.purpose": ["validation.required"],
        }

        string_amount = amir.create({**valid_loan, "details": {**details, "amount": "100000000"}})
        assert string_amount.data["errors"] == {"details.amount": ["validation.number.invalid"]}

        long_text = amir.create({**valid_loan, "details": {**details, "purpose": "x" * 121}})
        assert long_text.data["errors"] == {"details.purpose": ["validation.text.max"]}

    def test_validates_the_description_and_the_body_shape(self) -> None:
        amir = customer_api("amir")
        short = amir.create({**valid_loan, "description": "short"})
        expect_error(short, "validation")
        assert short.data["errors"] == {"description": ["validation.description.min"]}
        long = amir.create({**valid_loan, "description": "x" * 1001})
        assert long.data["errors"] == {"description": ["validation.description.max"]}
        assert amir.create({**valid_loan, "description": "x" * 1000}).status == 201
        assert amir.create({**valid_loan, "description": "x" * 10}).status == 201
        assert amir.create({**valid_loan, "description": "   short   "}).status == 400
        assert amir.create({**valid_loan, "description": 12345678901}).status == 400

        for details in ("text", ["a"], 5, None):
            reply = amir.create({**valid_loan, "details": details})
            expect_error(reply, "validation")
            assert list(reply.data["errors"]) == ["details"]
        missing = amir.create({})
        assert set(missing.data["errors"]) == {"serviceId", "description", "details"}

    def test_an_unknown_service_is_not_found(self) -> None:
        expect_error(
            customer_api("amir").create({**valid_loan, "serviceId": "unknown-service"}), "not_found"
        )
        long_id = customer_api("amir").create({**valid_loan, "serviceId": "x" * 65})
        expect_error(long_id, "validation")

    def test_the_service_decides_the_department_not_the_client(self) -> None:
        reply = customer_api("amir").create(
            {
                "serviceId": "rent-subsidy",
                "description": "Rent went up this year, please help.",
                "details": {"monthlyRent": 10_000_000, "householdSize": 3},
            }
        )
        assert reply.data["departmentId"] == "housing"

    def test_a_failed_filing_leaves_nothing_behind(self) -> None:
        amir = customer_api("amir")
        requests, events, audits = (
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            AuditLog.objects.count(),
        )
        amir.create({**valid_loan, "details": {"amount": 1}})
        amir.create({**valid_loan, "serviceId": "nope"})
        assert (
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            AuditLog.objects.count(),
        ) == (requests, events, audits)

    def test_filing_is_audited_with_the_tracking_code(self) -> None:
        created = customer_api("amir").create(valid_loan).data
        entry = AuditLog.objects.get(action="request_created")
        assert entry.target == created["trackingCode"]
        assert str(entry.actor_id) == uid("c-amir")

    def test_the_new_request_shows_up_in_the_applicants_own_list(self) -> None:
        amir = customer_api("amir")
        created = amir.create(valid_loan).data
        mine = amir.mine().data
        assert mine[0]["id"] == created["id"]  # newest activity first
        assert len(mine) == 4

    def test_many_requests_get_many_distinct_tracking_codes(self) -> None:
        amir = customer_api("amir")
        codes = {amir.create(valid_loan).data["trackingCode"] for _ in range(25)}
        assert len(codes) == 25


class TestServiceAvailability:
    def test_is_public_to_read_and_admin_only_to_change(self) -> None:
        reply = Api().get("/api/catalog/services/")
        assert len(reply.data) == 8
        assert all(service["isActive"] for service in reply.data)
        expect_error(
            Api().patch("/api/catalog/services/personal-loan/active/", {"isActive": False}),
            "unauthenticated",
        )

    def test_stops_new_requests_for_a_switched_off_service_and_resumes_when_it_is_back_on(
        self,
    ) -> None:
        admin = staff_api("admin")
        paused = admin.patch("/api/catalog/services/personal-loan/active/", {"isActive": False})
        assert paused.status == 200
        assert paused.data["isActive"] is False
        assert paused.data["id"] == "personal-loan"
        assert Api().get("/api/catalog/services/personal-loan/").data["isActive"] is False

        amir = customer_api("amir")
        expect_error(amir.create(valid_loan), "service_unavailable")
        # Other services keep working, and the department's other service too.
        other = amir.create(
            {
                "serviceId": "business-loan",
                "description": "Working capital for the workshop.",
                "details": {"amount": 100_000_000, "termMonths": "12", "businessField": "Printing"},
            }
        )
        assert other.status == 201

        admin.patch("/api/catalog/services/personal-loan/active/", {"isActive": True})
        assert amir.create(valid_loan).data["status"] == "pending_review"
        expect_error(Api().get("/api/catalog/services/nope/"), "not_found")

    def test_pausing_a_service_does_not_hide_or_freeze_existing_requests(self) -> None:
        staff_api("admin").patch("/api/catalog/services/personal-loan/active/", {"isActive": False})
        reza = staff_api("reza")
        assert reza.request(REQ.loan_in_progress).status == 200
        assert reza.transition(REQ.loan_pending, "in_progress").status == 200

    def test_the_toggle_is_strict_about_its_input(self) -> None:
        admin = staff_api("admin")
        for body in (
            {},
            {"isActive": "false"},
            {"isActive": 0},
            {"isActive": None},
            {"isActive": [True]},
        ):
            reply = admin.patch("/api/catalog/services/personal-loan/active/", body)
            expect_error(reply, "validation")
            assert list(reply.data["errors"]) == ["isActive"]
        assert Api().get("/api/catalog/services/personal-loan/").data["isActive"] is True

    def test_an_unknown_service_cannot_be_toggled(self) -> None:
        expect_error(
            staff_api("admin").patch("/api/catalog/services/nope/active/", {"isActive": False}),
            "not_found",
        )

    def test_a_customer_filing_into_an_unknown_service_is_not_found_even_when_paused_ones_exist(
        self,
    ) -> None:
        staff_api("admin").patch("/api/catalog/services/personal-loan/active/", {"isActive": False})
        expect_error(customer_api("amir").create({**valid_loan, "serviceId": "nope"}), "not_found")

    def test_pausing_and_resuming_are_separate_audit_events_whose_target_carries_no_wording(
        self,
    ) -> None:
        admin = staff_api("admin")
        admin.patch("/api/catalog/services/steel-supply/active/", {"isActive": False})
        admin.patch("/api/catalog/services/steel-supply/active/", {"isActive": True})
        resumed, paused = admin.audit().data["items"][:2]
        assert (resumed["action"], resumed["target"]) == ("service_resumed", "steel-supply")
        assert (paused["action"], paused["target"]) == ("service_paused", "steel-supply")


class TestTeamManagement:
    def test_lists_accounts_without_any_credentials(self) -> None:
        reply = staff_api("admin").get("/api/staff/")
        assert reply.status == 200
        assert sorted(account["role"] for account in reply.data) == [
            "admin",
            "staff",
            "staff",
            "staff",
            "staff",
        ]
        assert [account["username"] for account in reply.data] == [
            "admin",
            "ali",
            "maryam",
            "reza",
            "sara",
        ]
        assert not any(word in json.dumps(reply.data) for word in ("password", "Hash", "Salt"))
        assert all("nationalId" not in account for account in reply.data)  # no customers here

    def test_creates_staff_who_can_sign_in_and_are_confined_to_the_departments_they_were_given(
        self,
    ) -> None:
        admin = staff_api("admin")
        reply = admin.post("/api/staff/", {**NEW_STAFF, "role": "admin", "isActive": False})
        assert reply.status == 201
        created = reply.data
        assert created["role"] == "staff"
        assert created["username"] == "nima"
        assert created["departmentIds"] == ["vehicle"]
        assert created["isActive"] is True
        assert created["name"] == {"fa": "نیما احمدی", "en": "Nima Ahmadi"}

        nima = staff_api("nima", NEW_STAFF["password"])
        page = nima.queue().data
        assert all(item["departmentId"] == "vehicle" for item in page["items"])
        expect_error(nima.queue(departmentId="loan"), "forbidden")
        expect_error(nima.get("/api/staff/"), "forbidden")

    def test_new_staff_are_audited_by_username(self) -> None:
        staff_api("admin").post("/api/staff/", NEW_STAFF)
        entry = AuditLog.objects.get(action="staff_created")
        assert entry.target == "nima"
        assert entry.actor_role == "admin"

    def test_refuses_duplicate_usernames_weak_passwords_and_accounts_with_no_department(
        self,
    ) -> None:
        admin = staff_api("admin")
        expect_error(admin.post("/api/staff/", {**NEW_STAFF, "username": "reza"}), "username_taken")
        expect_error(
            admin.post("/api/staff/", {**NEW_STAFF, "username": "admin"}), "username_taken"
        )
        for override, field in (
            ({"password": "short1"}, "password"),
            ({"password": "alllowercase"}, "password"),
            ({"departmentIds": []}, "departmentIds"),
            ({"departmentIds": ["space_travel"]}, "departmentIds"),
            ({"departmentIds": "loan"}, "departmentIds"),
            ({"departmentIds": [1]}, "departmentIds"),
            ({"username": "Bad Name"}, "username"),
            ({"username": "Nima"}, "username"),  # not silently lower-cased
            ({"username": " nima"}, "username"),
            ({"username": "1nima"}, "username"),
            ({"username": "ni"}, "username"),
            ({"username": "n" * 21}, "username"),
            ({"nameFa": ""}, "nameFa"),
            ({"nameEn": "N"}, "nameEn"),
            ({"nameEn": "x" * 61}, "nameEn"),
        ):
            reply = admin.post("/api/staff/", {**NEW_STAFF, **override})
            expect_error(reply, "validation")
            assert field in reply.data["errors"], override
        assert not User.objects.filter(username="nima").exists()

    def test_duplicate_departments_are_collapsed(self) -> None:
        created = staff_api("admin").post(
            "/api/staff/", {**NEW_STAFF, "departmentIds": ["loan", "vehicle", "loan"]}
        )
        assert created.data["departmentIds"] == ["loan", "vehicle"]

    def test_a_username_check_happens_after_validation_and_is_case_exact(self) -> None:
        admin = staff_api("admin")
        # "REZA" is not a valid username shape, so it's a validation error, not "taken".
        expect_error(admin.post("/api/staff/", {**NEW_STAFF, "username": "REZA"}), "validation")

    def test_changes_a_staff_members_access_immediately_and_un_assigns_stranded_work(self) -> None:
        reza = staff_api("reza")
        assert reza.queue().data["total"] == 2

        admin = staff_api("admin")
        updated = admin.patch(
            f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["housing"], "isActive": True}
        )
        assert updated.status == 200
        assert updated.data["departmentIds"] == ["housing"]

        stranded = admin.request(REQ.loan_in_progress).data  # was Reza's, in the loan department
        assert stranded["assignee"] is None
        last = stranded["timeline"][-1]
        assert last["kind"] == "assigned"
        assert last["assignee"] is None
        assert last["actor"]["role"] == "admin"
        assert stranded["updatedAt"] == last["at"]

        # The SAME token he already held, no re-login:
        page = reza.queue().data
        assert page["total"] == 2
        assert all(item["departmentId"] == "housing" for item in page["items"])
        expect_error(reza.request(REQ.loan_in_progress), "forbidden")
        expect_error(reza.transition(REQ.loan_pending, "in_progress"), "forbidden")
        assert reza.me().data["departmentIds"] == ["housing"]

    def test_adding_a_department_keeps_existing_work(self) -> None:
        admin = staff_api("admin")
        admin.patch(
            f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["loan", "vehicle"], "isActive": True}
        )
        assert admin.request(REQ.loan_in_progress).data["assignee"]["id"] == uid("u-reza")
        assert staff_api("reza").queue().data["total"] == 4

    def test_only_open_work_in_a_lost_department_is_released(self) -> None:
        ServiceRequest.objects.filter(pk=REQ.raw_closed).update(assignee_id=uid("u-reza"))
        # raw_closed is closed and now Reza's; he never had raw_material, so removing nothing
        # changes it, but removing *loan* must leave closed history alone as well.
        ServiceRequest.objects.filter(pk=REQ.vehicle_rejected).update(
            assignee_id=uid("u-reza"), status="closed"
        )
        admin = staff_api("admin")
        admin.patch(
            f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["housing"], "isActive": True}
        )
        assert admin.request(REQ.vehicle_rejected).data["assignee"]["id"] == uid("u-reza")
        assert admin.request(REQ.raw_closed).data["assignee"]["id"] == uid("u-reza")
        assert admin.request(REQ.loan_in_progress).data["assignee"] is None

    def test_deactivating_someone_signs_them_out_frees_their_open_work_and_keeps_closed_history(
        self,
    ) -> None:
        sara = staff_api("sara")
        admin = staff_api("admin")
        reply = admin.patch(
            f"/api/staff/{uid('u-sara')}/", {"departmentIds": ["raw_material"], "isActive": False}
        )
        assert reply.data["isActive"] is False

        assert admin.request(REQ.raw_needs_correction).data["assignee"] is None  # open → freed
        assert admin.request(REQ.raw_closed).data["assignee"]["id"] == uid("u-sara")  # history kept

        expect_error(sara.me(), "unauthenticated")
        expect_error(sara.queue(), "unauthenticated")
        assert not AccessToken.objects.filter(
            user_id=uid("u-sara"), revoked_at__isnull=True
        ).exists()

        admin.patch(
            f"/api/staff/{uid('u-sara')}/", {"departmentIds": ["raw_material"], "isActive": True}
        )
        assert staff_api("sara").me().data["username"] == "sara"
        expect_error(sara.me(), "unauthenticated")  # the old session stays dead

    def test_a_deactivated_member_is_not_offered_for_assignment(self) -> None:
        admin = staff_api("admin")
        admin.patch(
            f"/api/staff/{uid('u-sara')}/", {"departmentIds": ["raw_material"], "isActive": False}
        )
        assert admin.assignable("raw_material").data == []

    def test_wont_edit_administrators_customers_or_unknown_accounts(self) -> None:
        admin = staff_api("admin")
        edit = {"departmentIds": ["loan"], "isActive": False}
        expect_error(admin.patch(f"/api/staff/{uid('u-admin')}/", edit), "forbidden")
        expect_error(admin.patch(f"/api/staff/{uid('c-amir')}/", edit), "forbidden")
        expect_error(admin.patch("/api/staff/ghost/", edit), "not_found")
        expect_error(
            admin.patch("/api/staff/00000000-0000-0000-0000-000000000000/", edit), "not_found"
        )
        expect_error(
            admin.patch(f"/api/staff/{uid('u-reza')}/", {"departmentIds": [], "isActive": True}),
            "validation",
        )
        assert User.objects.get(pk=uid("u-admin")).is_active is True
        assert User.objects.get(pk=uid("c-amir")).is_active is True

    def test_an_update_needs_both_fields_with_the_right_types(self) -> None:
        admin = staff_api("admin")
        url = f"/api/staff/{uid('u-reza')}/"
        for body in (
            {},
            {"departmentIds": ["loan"]},
            {"isActive": True},
            {"departmentIds": ["loan"], "isActive": "yes"},
            {"departmentIds": ["loan"], "isActive": 1},
            {"departmentIds": "loan", "isActive": True},
        ):
            expect_error(admin.patch(url, body), "validation")

    def test_updates_are_audited_by_username(self) -> None:
        staff_api("admin").patch(
            f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["loan"], "isActive": True}
        )
        entry = AuditLog.objects.get(action="staff_updated")
        assert entry.target == "reza"

    def test_a_change_that_changes_nothing_still_succeeds(self) -> None:
        reply = staff_api("admin").patch(
            f"/api/staff/{uid('u-reza')}/", {"departmentIds": ["loan"], "isActive": True}
        )
        assert reply.status == 200
        assert staff_api("reza").queue().data["total"] == 2

    def test_other_http_verbs_are_not_offered(self) -> None:
        admin = staff_api("admin")
        assert admin.call("delete", f"/api/staff/{uid('u-reza')}/").status == 405
        assert admin.call("put", f"/api/staff/{uid('u-reza')}/", {}).status == 405
        assert admin.call("delete", "/api/staff/").status == 405
        assert User.objects.filter(pk=uid("u-reza")).exists()


class TestPasswordsOfNewStaff:
    def test_a_new_staff_password_is_stored_hashed_and_works(self) -> None:
        staff_api("admin").post("/api/staff/", NEW_STAFF)
        stored = User.objects.get(username="nima")
        assert NEW_STAFF["password"] not in stored.password
        assert staff_api("nima", NEW_STAFF["password"]).me().status == 200
        assert (
            Api()
            .post("/api/auth/login/staff/", {"username": "nima", "password": DEMO_PASSWORD})
            .status
            == 401
        )
