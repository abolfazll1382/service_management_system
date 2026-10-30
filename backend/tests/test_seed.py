"""The demo data (port of the frontend's ``seed.test.ts``), checked as it sits in the database."""

from __future__ import annotations

import pytest
from django.contrib.auth.hashers import check_password

from apps.audit.models import AuditLog
from apps.catalog.fields import clean_details
from apps.catalog.models import Service
from apps.core.choices import DEPARTMENT_IDS
from apps.core.demo.seed_data import (
    DEMO_PASSWORD,
    SEED_REQUESTS,
    SEED_USERS,
    seed_id,
)
from apps.core.demo.service import DemoService
from apps.core.persian import is_valid_national_id
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.requests.workflow import ALLOWED_TRANSITIONS
from apps.users.models import User

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]


def unique(values: list[str | None]) -> bool:
    present = [value for value in values if value]
    return len(set(present)) == len(present)


class TestSeedAccounts:
    def test_the_documented_demo_password_opens_every_account(self) -> None:
        for user in User.objects.all():
            assert check_password(DEMO_PASSWORD, user.password), user.pk

    def test_the_stored_value_is_a_salted_hash_not_the_password(self) -> None:
        for user in User.objects.all():
            assert DEMO_PASSWORD not in user.password
            assert "$" in user.password

    def test_ids_usernames_national_ids_and_phones_are_unique(self) -> None:
        users = list(User.objects.all())
        assert len(users) == len(SEED_USERS) == 8
        assert unique([str(user.pk) for user in users])
        assert unique([user.username for user in users])
        assert unique([user.national_id for user in users])
        assert unique([user.phone for user in users])

    def test_customers_have_valid_national_ids_and_staff_real_departments(self) -> None:
        for user in User.objects.all():
            if user.role == "customer":
                assert user.national_id is not None
                assert is_valid_national_id(user.national_id), user.full_name
            if user.role == "staff":
                assert user.department_ids
                assert set(user.department_ids) <= set(DEPARTMENT_IDS)

    def test_staff_departments_match_the_brief(self) -> None:
        by_username = {user.username: user for user in User.objects.exclude(role="customer")}
        assert by_username["reza"].department_ids == ["loan"]
        assert by_username["sara"].department_ids == ["raw_material"]
        assert by_username["ali"].department_ids == ["vehicle"]
        assert by_username["maryam"].department_ids == ["housing"]
        assert by_username["admin"].role == "admin"

    def test_ids_are_deterministic(self) -> None:
        assert User.objects.get(username="reza").pk == seed_id("u-reza")
        assert str(seed_id("u-reza")) == str(seed_id("u-reza"))
        assert seed_id("u-reza") != seed_id("u-sara")


class TestSeedRequests:
    def test_point_at_real_customers_and_services_in_the_services_own_department(self) -> None:
        requests = list(ServiceRequest.objects.select_related("service", "customer"))
        assert len(requests) == 8
        for request in requests:
            assert request.department == request.service.department, request.pk
            assert request.customer.role == "customer"
            assert len(request.tracking_code) == 10
            assert request.customer_national_id == request.customer.national_id
            assert request.customer_phone == request.customer.phone
            assert request.customer_full_name == request.customer.full_name
        assert len({request.tracking_code for request in requests}) == 8

    def test_details_satisfy_their_services_own_validator(self) -> None:
        for request in ServiceRequest.objects.select_related("service"):
            cleaned, errors = clean_details(request.service.field_definitions, request.details)
            assert errors == {}, f"{request.pk}: {request.details}"
            assert cleaned == request.details

    def test_have_a_coherent_history_legal_moves_in_time_order_ending_at_the_stored_status(
        self,
    ) -> None:
        for request in ServiceRequest.objects.all():
            events = list(request.events.order_by("sequence"))
            assert [event.sequence for event in events] == list(range(len(events)))
            assert events[0].kind == "submitted"
            status = "pending_review"
            previous = events[0].at
            for event in events:
                assert event.at >= previous, f"{request.pk} out of order"
                previous = event.at
                if event.kind == "status_changed":
                    assert event.from_status == status
                    assert event.to_status in ALLOWED_TRANSITIONS[status]
                    status = event.to_status
            assert request.status == status
            assert request.updated_at == events[-1].at

    def test_are_assigned_only_to_staff_of_the_requests_department(self) -> None:
        for request in ServiceRequest.objects.exclude(assignee=None).select_related("assignee"):
            assert request.assignee is not None
            assert request.assignee.role == "staff"
            assert request.department in request.assignee.department_ids

    def test_cover_every_department_and_most_statuses(self) -> None:
        requests = ServiceRequest.objects.all()
        assert {request.department for request in requests} == set(DEPARTMENT_IDS)
        assert len({request.status for request in requests}) >= 5

    def test_the_events_carry_the_actors_as_they_were(self) -> None:
        event = TimelineEvent.objects.filter(
            request_id=seed_id("req-seed-1"), kind="assigned"
        ).get()
        assert event.actor_role == "staff"
        assert event.actor_name_en == "Reza Karimi"
        assert event.assignee_name_en == "Reza Karimi"


class TestSeeding:
    def test_services_are_created_too(self) -> None:
        assert Service.objects.count() == 8

    def test_seeding_again_changes_nothing(self) -> None:
        before = (
            User.objects.count(),
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            Service.objects.count(),
        )
        report = DemoService.seed()
        assert (report.users_created, report.requests_created, report.services_created) == (0, 0, 0)
        assert before == (
            User.objects.count(),
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            Service.objects.count(),
        )

    def test_seeding_never_overwrites_what_someone_changed_on_purpose(self) -> None:
        User.objects.filter(pk=seed_id("u-reza")).update(is_active=False)
        ServiceRequest.objects.filter(pk=seed_id("req-seed-5")).update(status="rejected")
        DemoService.seed()
        assert User.objects.get(pk=seed_id("u-reza")).is_active is False
        assert ServiceRequest.objects.get(pk=seed_id("req-seed-5")).status == "rejected"

    def test_seeding_fills_in_only_what_is_missing(self) -> None:
        ServiceRequest.objects.filter(pk=seed_id("req-seed-6")).delete()
        report = DemoService.seed()
        assert report.requests_created == 1
        assert ServiceRequest.objects.filter(pk=seed_id("req-seed-6")).exists()

    def test_seeding_writes_no_audit_entries(self) -> None:
        assert AuditLog.objects.count() == 0

    def test_a_foreign_account_squatting_a_seed_username_is_reported_not_overwritten(self) -> None:
        from apps.core.exceptions import UsernameTakenError

        # Free the username: nothing may reference the real account any more.
        TimelineEvent.objects.all().delete()
        ServiceRequest.objects.all().delete()
        User.objects.get(username="reza").delete()
        impostor = User.objects.create(
            role="staff",
            username="reza",
            name_fa="جعلی",
            name_en="Impostor",
            department_ids=["loan"],
            password="x",
        )
        with pytest.raises(UsernameTakenError):
            DemoService.seed()
        assert User.objects.get(username="reza").pk == impostor.pk


def test_the_seed_script_has_the_eight_stories_the_tests_rely_on() -> None:
    assert [seed.key for seed in SEED_REQUESTS] == [f"req-seed-{n}" for n in range(1, 9)]
