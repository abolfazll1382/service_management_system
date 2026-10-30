"""Who may see and do what over HTTP (port of the frontend's ``api.rbac.test.ts``)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from apps.audit.models import AuditLog
from apps.core.choices import DEPARTMENT_IDS
from apps.requests.models import ServiceRequest, TimelineEvent
from tests.helpers import (
    REQ,
    Api,
    customer_api,
    expect_error,
    staff_api,
    uid,
    valid_loan,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]


def ids_of(page: dict[str, Any]) -> list[str]:
    return sorted(item["id"] for item in page["items"])


def world() -> tuple[Any, ...]:
    """Everything a refused call must leave untouched."""
    return (
        list(
            ServiceRequest.objects.order_by("pk").values_list(
                "pk", "status", "assignee_id", "updated_at"
            )
        ),
        TimelineEvent.objects.count(),
        AuditLog.objects.count(),
    )


class TestStaffSeeOnlyTheirDepartmentsQueue:
    EXPECTED = [
        ("reza", "loan", [REQ.loan_in_progress, REQ.loan_pending]),
        ("sara", "raw_material", [REQ.raw_needs_correction, REQ.raw_closed]),
        ("ali", "vehicle", [REQ.vehicle_pending, REQ.vehicle_rejected]),
        ("maryam", "housing", [REQ.housing_approved, REQ.housing_in_progress]),
    ]

    @pytest.mark.parametrize(("username", "department", "ids"), EXPECTED)
    def test_each_member_sees_only_their_own_department(
        self, username: str, department: str, ids: list[str]
    ) -> None:
        page = staff_api(username).queue().data
        assert ids_of(page) == sorted(ids)
        assert all(item["departmentId"] == department for item in page["items"])
        assert page["total"] == 2
        assert sum(page["counts"].values()) == 2

    def test_an_explicit_request_for_another_departments_queue_is_refused(self) -> None:
        reza = staff_api("reza")
        for other in (d for d in DEPARTMENT_IDS if d != "loan"):
            expect_error(reza.queue(departmentId=other), "forbidden")
        assert reza.queue(departmentId="loan").data["total"] == 2

    def test_search_cannot_widen_the_scope(self) -> None:
        vehicle_code = ServiceRequest.objects.get(pk=REQ.vehicle_pending).tracking_code
        assert staff_api("reza").queue(search=vehicle_code).data["total"] == 0
        assert staff_api("admin").queue(search=vehicle_code).data["total"] == 1

    def test_no_filter_combination_can_widen_the_scope(self) -> None:
        reza = staff_api("reza")
        for params in (
            {"assignment": "unassigned"},
            {"assignment": "mine"},
            {"status": "pending_review"},
            {"search": ""},
            {"pageSize": 50},
            {"search": "Karimi"},  # a name shared across departments
        ):
            page = reza.queue(**params).data
            assert {item["departmentId"] for item in page["items"]} <= {"loan"}, params

    def test_an_administrator_sees_every_department(self) -> None:
        page = staff_api("admin").queue(pageSize=50).data
        assert page["total"] == 8
        assert {item["departmentId"] for item in page["items"]} == set(DEPARTMENT_IDS)

    def test_an_administrator_may_narrow_to_one_department(self) -> None:
        page = staff_api("admin").queue(departmentId="vehicle").data
        assert ids_of(page) == sorted([REQ.vehicle_pending, REQ.vehicle_rejected])

    def test_filters_search_and_paging_work_inside_the_scope(self) -> None:
        admin = staff_api("admin")
        assert admin.queue(status="pending_review").data["total"] == 2
        assert admin.queue(assignment="unassigned").data["total"] == 2
        assert admin.queue(search="Hossein").data["total"] == 3
        assert admin.queue(search="hossein").data["total"] == 3  # case-insensitive
        assert admin.queue(search="۰۵۹۲۸۴۶۷۱۷").data["total"] == 3  # Persian digits
        assert admin.queue(search="٠٥٩٢٨٤٦٧١٧").data["total"] == 3  # Arabic-Indic digits
        assert admin.queue(search="09121234567").data["total"] == 3  # by phone
        second = admin.queue(pageSize=3, page=2).data
        assert (second["total"], second["page"], second["pageSize"]) == (8, 2, 3)
        assert len(second["items"]) == 3
        assert len(admin.queue(pageSize=3, page=3).data["items"]) == 2
        beyond = admin.queue(pageSize=3, page=99).data
        assert beyond["items"] == []
        assert beyond["total"] == 8

    def test_searching_by_tracking_code_and_applicant_name(self) -> None:
        admin = staff_api("admin")
        code = ServiceRequest.objects.get(pk=REQ.raw_closed).tracking_code
        assert ids_of(admin.queue(search=code).data) == [REQ.raw_closed]
        assert ids_of(admin.queue(search=code[2:7]).data) == [REQ.raw_closed]
        assert admin.queue(search="امیر").data["total"] == 3
        assert admin.queue(search="zzzz").data["total"] == 0

    def test_search_treats_wildcards_literally(self) -> None:
        admin = staff_api("admin")
        assert admin.queue(search="%").data["total"] == 0
        assert admin.queue(search="_").data["total"] == 0
        assert admin.queue(search="'; DROP TABLE users; --").data["total"] == 0

    def test_my_work_is_the_callers_own_assignments(self) -> None:
        assert ids_of(staff_api("reza").queue(assignment="mine").data) == [REQ.loan_in_progress]
        assert staff_api("admin").queue(assignment="mine").data["total"] == 0

    def test_status_counts_ignore_the_status_filter_but_respect_everything_else(self) -> None:
        admin = staff_api("admin")
        everything = admin.queue().data
        only_pending = admin.queue(status="pending_review").data
        assert only_pending["counts"] == everything["counts"]
        assert len(only_pending["items"]) == 2
        assert everything["counts"] == {
            "pending_review": 2,
            "in_progress": 2,
            "needs_correction": 1,
            "approved": 1,
            "rejected": 1,
            "closed": 1,
        }
        scoped = admin.queue(departmentId="loan", status="closed").data
        assert scoped["counts"] == {
            "pending_review": 1,
            "in_progress": 1,
            "needs_correction": 0,
            "approved": 0,
            "rejected": 0,
            "closed": 0,
        }
        assert scoped["items"] == []

    def test_the_queue_is_ordered_by_latest_activity_with_a_total_order(self) -> None:
        expected = [
            str(pk)
            for pk in ServiceRequest.objects.order_by(
                "-updated_at", "-submitted_at", "id"
            ).values_list("pk", flat=True)
        ]
        page = staff_api("admin").queue(pageSize=50).data
        assert [item["id"] for item in page["items"]] == expected

    def test_pages_neither_skip_nor_repeat(self) -> None:
        admin = staff_api("admin")
        seen: list[str] = []
        for number in range(1, 5):
            seen += [item["id"] for item in admin.queue(pageSize=3, page=number).data["items"]]
        assert len(seen) == len(set(seen)) == 8

    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"status": "teleported"}, "status"),
            ({"departmentId": "space_travel"}, "departmentId"),
            ({"assignment": "everyone"}, "assignment"),
            ({"page": 0}, "page"),
            ({"page": "abc"}, "page"),
            ({"page": -1}, "page"),
            ({"pageSize": 0}, "pageSize"),
            ({"pageSize": 51}, "pageSize"),
            ({"pageSize": "many"}, "pageSize"),
            ({"search": "x" * 101}, "search"),
        ],
    )
    def test_bad_query_parameters_are_validation_errors_by_field(
        self, params: dict[str, Any], field: str
    ) -> None:
        reply = staff_api("admin").queue(**params)
        expect_error(reply, "validation")
        assert list(reply.data["errors"]) == [field]

    def test_empty_query_parameters_count_as_absent(self) -> None:
        reply = staff_api("admin").get(
            "/api/requests/queue/",
            {
                "status": "",
                "departmentId": "",
                "assignment": "",
                "search": "",
                "page": "",
                "pageSize": "",
            },
        )
        assert reply.status == 200
        assert reply.data["total"] == 8
        assert reply.data["pageSize"] == 10

    def test_the_default_page_size_is_ten_and_the_envelope_is_complete(self) -> None:
        page = staff_api("admin").queue().data
        assert set(page) == {"items", "total", "page", "pageSize", "counts"}
        assert (page["page"], page["pageSize"]) == (1, 10)


class TestStaffCannotActOnAnotherDepartmentsRequest:
    def test_is_refused_for_read_transition_assignment_and_messages_and_nothing_changes(
        self,
    ) -> None:
        reza = staff_api("reza")
        before = world()
        expect_error(reza.request(REQ.vehicle_pending), "forbidden")
        expect_error(reza.transition(REQ.vehicle_pending, "in_progress"), "forbidden")
        expect_error(reza.assign(REQ.vehicle_pending, uid("u-reza")), "forbidden")
        expect_error(reza.assign(REQ.vehicle_pending, None), "forbidden")
        expect_error(reza.message(REQ.vehicle_pending, "hello", "public"), "forbidden")
        expect_error(reza.message(REQ.vehicle_pending, "note", "internal"), "forbidden")
        expect_error(reza.assignable("vehicle"), "forbidden")
        assert world() == before

    def test_applies_to_every_pair_of_departments(self) -> None:
        owner = {"reza": "loan", "sara": "raw_material", "ali": "vehicle", "maryam": "housing"}
        for username, own in owner.items():
            client = staff_api(username)
            for request in ServiceRequest.objects.all():
                reply = client.request(str(request.pk))
                if request.department == own:
                    assert reply.status == 200
                    assert reply.data["id"] == str(request.pk)
                else:
                    expect_error(reply, "forbidden")

    def test_an_unknown_request_is_not_found_even_for_staff(self) -> None:
        reza = staff_api("reza")
        expect_error(reza.request("00000000-0000-0000-0000-000000000000"), "not_found")
        expect_error(reza.request("req-nope"), "not_found")

    def test_does_not_offer_staff_the_administration_endpoints(self) -> None:
        reza = staff_api("reza")
        expect_error(reza.get("/api/staff/"), "forbidden")
        expect_error(
            reza.post(
                "/api/staff/",
                {
                    "nameFa": "نیما",
                    "nameEn": "Nima",
                    "username": "nima",
                    "password": "Welcome1pass",
                    "departmentIds": ["loan"],
                },
            ),
            "forbidden",
        )
        expect_error(
            reza.patch(
                f"/api/staff/{uid('u-sara')}/", {"departmentIds": ["loan"], "isActive": True}
            ),
            "forbidden",
        )
        expect_error(reza.audit(), "forbidden")
        expect_error(reza.post("/api/demo/reset/"), "forbidden")
        expect_error(
            reza.patch("/api/catalog/services/personal-loan/active/", {"isActive": False}),
            "forbidden",
        )
        expect_error(reza.create(valid_loan), "forbidden")
        expect_error(reza.mine(), "forbidden")

    def test_the_coarse_gate_runs_before_input_is_looked_at(self) -> None:
        reza = staff_api("reza")
        expect_error(reza.post("/api/staff/", {}), "forbidden")
        expect_error(reza.create({}), "forbidden")


class TestCustomersSeeOnlyTheirOwnRequests:
    def test_lists_just_the_callers_requests(self) -> None:
        mine = customer_api("amir").mine().data
        assert sorted(item["id"] for item in mine) == sorted(
            [REQ.loan_in_progress, REQ.vehicle_pending, REQ.housing_in_progress]
        )

    def test_the_list_is_newest_activity_first(self) -> None:
        mine = customer_api("amir").mine().data
        stamps = [item["updatedAt"] for item in mine]
        assert stamps == sorted(stamps, reverse=True)

    def test_somebody_elses_request_is_not_found_however_it_is_reached(self) -> None:
        maryam = customer_api("maryam")
        before = world()
        foreign = maryam.request(REQ.loan_in_progress)
        expect_error(foreign, "not_found")
        expect_error(maryam.message(REQ.loan_in_progress, "hi", "public"), "not_found")
        expect_error(maryam.transition(REQ.loan_in_progress, "approved"), "not_found")
        expect_error(maryam.assign(REQ.loan_in_progress, None), "not_found")
        expect_error(maryam.message(REQ.loan_in_progress, "hi", "internal"), "not_found")
        assert world() == before

    def test_a_foreign_id_and_a_missing_id_get_identical_answers(self) -> None:
        maryam = customer_api("maryam")
        foreign = maryam.request(REQ.loan_in_progress)
        missing = maryam.request("00000000-0000-0000-0000-000000000000")
        malformed = maryam.request("does-not-exist")
        assert foreign.status == missing.status == malformed.status == 404
        assert foreign.data == missing.data == malformed.data

    def test_cannot_act_as_staff_on_their_own_request(self) -> None:
        amir = customer_api("amir")
        before = world()
        expect_error(amir.transition(REQ.loan_in_progress, "approved"), "forbidden")
        expect_error(amir.assign(REQ.loan_in_progress, uid("u-reza")), "forbidden")
        expect_error(amir.message(REQ.loan_in_progress, "note", "internal"), "forbidden")
        expect_error(amir.queue(), "forbidden")
        expect_error(amir.assignable("loan"), "forbidden")
        expect_error(amir.get("/api/staff/"), "forbidden")
        expect_error(amir.audit(), "forbidden")
        expect_error(amir.post("/api/demo/reset/"), "forbidden")
        expect_error(
            amir.patch("/api/catalog/services/personal-loan/active/", {"isActive": False}),
            "forbidden",
        )
        assert world() == before

    def test_a_customer_cannot_see_who_else_has_an_account(self) -> None:
        amir = customer_api("amir")
        expect_error(amir.get("/api/staff/"), "forbidden")
        detail = amir.request(REQ.loan_in_progress).data
        text = json.dumps(detail, ensure_ascii=False)
        for national_id in ("1277348561", "0592846717"):
            assert national_id not in text


class TestAnonymousCallers:
    def test_everything_but_the_catalogue_needs_a_session(self) -> None:
        anonymous = Api()
        for reply in (
            anonymous.mine(),
            anonymous.create(valid_loan),
            anonymous.queue(),
            anonymous.request(REQ.loan_in_progress),
            anonymous.transition(REQ.loan_in_progress, "in_progress"),
            anonymous.assign(REQ.loan_in_progress, None),
            anonymous.message(REQ.loan_in_progress, "hi", "public"),
            anonymous.assignable("loan"),
            anonymous.audit(),
            anonymous.get("/api/staff/"),
            anonymous.post("/api/staff/", {}),
            anonymous.post("/api/demo/reset/"),
            anonymous.me(),
        ):
            expect_error(reply, "unauthenticated")

    def test_the_catalogue_is_public(self) -> None:
        reply = Api().get("/api/catalog/services/")
        assert reply.status == 200
        assert len(reply.data) == 8

    def test_authentication_is_decided_before_authorisation_and_validation(self) -> None:
        expect_error(Api().post("/api/requests/", {}), "unauthenticated")
        expect_error(Api().get("/api/requests/queue/", {"status": "nonsense"}), "unauthenticated")


class TestAdministrators:
    def test_run_the_system_but_cannot_file_requests_as_an_applicant(self) -> None:
        admin = staff_api("admin")
        expect_error(admin.create(valid_loan), "forbidden")
        expect_error(admin.mine(), "forbidden")


class TestInternalNotes:
    SECRET = "household register"

    def test_never_reach_the_applicant_in_any_response(self) -> None:
        maryam = customer_api("maryam")
        detail = maryam.request(REQ.housing_approved).data
        assert not any(
            event["kind"] == "message" and event["visibility"] == "internal"
            for event in detail["timeline"]
        )
        assert self.SECRET not in json.dumps(detail)
        assert self.SECRET not in json.dumps(maryam.mine().data)

    def test_the_applicants_timeline_has_exactly_the_public_events(self) -> None:
        staff_view = staff_api("maryam").request(REQ.housing_approved).data["timeline"]
        customer_view = customer_api("maryam").request(REQ.housing_approved).data["timeline"]
        public = [
            event
            for event in staff_view
            if not (event["kind"] == "message" and event["visibility"] == "internal")
        ]
        assert len(staff_view) == len(public) + 1
        assert customer_view == public

    @pytest.mark.parametrize("username", ["maryam", "admin"])
    def test_are_visible_to_the_departments_staff_and_to_administrators(
        self, username: str
    ) -> None:
        detail = staff_api(username).request(REQ.housing_approved).data
        assert self.SECRET in json.dumps(detail)

    def test_are_visible_in_the_queue_to_those_who_may_read_them(self) -> None:
        page = staff_api("maryam").queue().data
        assert self.SECRET in json.dumps(page)
        assert self.SECRET not in json.dumps(staff_api("reza").queue().data)

    def test_stay_hidden_from_the_applicant_when_staff_add_new_ones(self) -> None:
        sara = staff_api("sara")
        sara.message(REQ.raw_needs_correction, "Secret staff remark", "internal")
        sara.message(REQ.raw_needs_correction, "Visible to applicant", "public")
        text = json.dumps(customer_api("maryam").request(REQ.raw_needs_correction).data)
        assert "Visible to applicant" in text
        assert "Secret staff remark" not in text

    def test_the_response_to_the_staff_member_who_wrote_one_includes_it(self) -> None:
        reply = staff_api("sara").message(
            REQ.raw_needs_correction, "Secret staff remark", "internal"
        )
        assert reply.status == 201
        assert reply.data["timeline"][-1]["visibility"] == "internal"

    def test_an_internal_note_never_changes_the_status(self) -> None:
        reply = staff_api("sara").message(REQ.raw_needs_correction, "just a note", "internal")
        assert reply.data["status"] == "needs_correction"
