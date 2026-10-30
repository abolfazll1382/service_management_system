"""The database enforces the invariants itself: bad rows are refused whatever the app does."""

from __future__ import annotations

import itertools
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from django.db import DataError, IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.catalog.models import Service
from apps.core.db import violated_constraint
from apps.requests.models import ServiceRequest, TimelineEvent
from apps.users.models import AccessToken, User
from tests.helpers import REQ, uid, with_check_digit

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]

_counter = itertools.count(100)


@contextmanager
def violates(constraint: str) -> Iterator[None]:
    """The block must be refused by the named constraint (and leaves the transaction usable)."""
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        yield
    assert violated_constraint(caught.value) == constraint, str(caught.value)


def customer(**overrides: Any) -> User:
    number = next(_counter)
    values: dict[str, Any] = {
        "role": "customer",
        "full_name": "Test Person",
        "national_id": with_check_digit(f"{number:09d}"),
        "phone": f"0915{number:07d}",
        "postal_code": "1234567890",
        "address": "Some street 12",
        "password": "x",
    }
    return User.objects.create(**{**values, **overrides})


def staff(**overrides: Any) -> User:
    number = next(_counter)
    values: dict[str, Any] = {
        "role": "staff",
        "username": f"worker{number}",
        "name_fa": "کارمند",
        "name_en": "Worker",
        "department_ids": ["loan"],
        "password": "x",
    }
    return User.objects.create(**{**values, **overrides})


def request_row(**overrides: Any) -> ServiceRequest:
    owner = User.objects.get(pk=uid("c-amir"))
    now = timezone.now()
    values: dict[str, Any] = {
        "tracking_code": f"{next(_counter):010d}",
        "customer": owner,
        "customer_full_name": owner.full_name,
        "customer_national_id": owner.national_id,
        "customer_phone": owner.phone,
        "department": "loan",
        "service_id": "personal-loan",
        "description": "A description that is long enough.",
        "details": {},
        "submitted_at": now,
        "updated_at": now,
    }
    return ServiceRequest.objects.create(**{**values, **overrides})


def event_row(request_id: Any = REQ.loan_pending, **overrides: Any) -> TimelineEvent:
    actor = User.objects.get(pk=uid("u-reza"))
    values: dict[str, Any] = {
        "request_id": request_id,
        "sequence": 50,
        "kind": "message",
        "at": timezone.now(),
        "actor": actor,
        "actor_role": "staff",
        "actor_name_fa": "رضا",
        "actor_name_en": "Reza",
        "visibility": "public",
        "body": "hello",
    }
    return TimelineEvent.objects.create(**{**values, **overrides})


class TestUsers:
    def test_valid_rows_of_each_role_are_accepted(self) -> None:
        customer()
        staff()
        User.objects.create(
            role="admin", username="boss", name_fa="مدیر", name_en="Boss", password="x"
        )

    @pytest.mark.parametrize(
        "make",
        [
            lambda: customer(username="sneaky"),  # a customer with a username
            lambda: customer(name_en="Sneaky"),
            lambda: customer(full_name=None),
            lambda: customer(address=None),
            lambda: customer(department_ids=["loan"]),
            lambda: staff(department_ids=[]),  # a staff member with no department
            lambda: staff(national_id="1234567890"),  # a staff member with customer columns
            lambda: staff(full_name="X"),
            lambda: staff(username=None),
            lambda: User.objects.create(
                role="admin",
                username="boss",
                name_fa="م",
                name_en="B",
                department_ids=["loan"],
                password="x",
            ),
            lambda: User.objects.create(
                role="ghost", username="boss", name_fa="م", name_en="B", password="x"
            ),
        ],
    )
    def test_a_row_whose_columns_do_not_fit_its_role_is_refused(self, make: Any) -> None:
        with violates("user_shape_matches_role"):
            make()

    def test_unknown_departments_are_refused(self) -> None:
        with violates("user_departments_known"):
            staff(department_ids=["loan", "space_travel"])

    @pytest.mark.parametrize("value", ["123", "00458139a2", "004581392 ", "۰۰۴۵۸۱۳۹۲۲", ""])
    def test_a_national_id_must_be_ten_ascii_digits(self, value: str) -> None:
        with violates("user_national_id_format"):
            customer(national_id=value)

    @pytest.mark.parametrize("value", ["123", "08151112233", "0915111223", "0915111223a"])
    def test_a_phone_must_be_eleven_digits_starting_09(self, value: str) -> None:
        with violates("user_phone_format"):
            customer(phone=value)

    @pytest.mark.parametrize("value", ["123", "abcdefghij", ""])
    def test_a_postal_code_must_be_ten_digits(self, value: str) -> None:
        with violates("user_postal_code_format"):
            customer(postal_code=value)

    @pytest.mark.parametrize("value", ["Reza", "1abc", "ab", "has space", "a-b-c", ""])
    def test_a_username_is_lower_case_by_construction(self, value: str) -> None:
        with violates("user_username_format"):
            staff(username=value)

    def test_values_longer_than_their_column_are_refused(self) -> None:
        for overrides in (
            {"national_id": "12345678901"},
            {"phone": "091511122334"},
            {"postal_code": "12345678901"},
            {"full_name": "x" * 101},
            {"address": "x" * 201},
        ):
            with pytest.raises(DataError), transaction.atomic():
                customer(**overrides)
        with pytest.raises(DataError), transaction.atomic():
            staff(username="a" * 21)

    def test_national_ids_phones_and_usernames_are_unique(self) -> None:
        with violates("user_national_id_unique"):
            customer(national_id="0045813922")
        with violates("user_phone_unique"):
            customer(phone="09121234567")
        with violates("user_username_unique"):
            staff(username="reza")
        with violates("user_username_unique"):
            staff(username="admin")  # administrators and staff share one namespace

    def test_unique_columns_that_are_null_never_collide(self) -> None:
        staff()
        staff()
        assert User.objects.filter(role="staff").count() == 6

    def test_deleting_a_user_that_has_requests_is_blocked(self) -> None:
        with pytest.raises(ProtectedError):
            User.objects.get(pk=uid("c-amir")).delete()
        with pytest.raises(ProtectedError):
            User.objects.get(pk=uid("u-reza")).delete()

    def test_deleting_a_user_removes_their_tokens_and_keeps_their_audit_trail(self) -> None:
        worker = staff()
        now = timezone.now()
        AccessToken.objects.create(
            user=worker, key_hash="a" * 64, expires_at=now + timedelta(hours=1)
        )
        AuditLog.objects.create(
            actor=worker,
            actor_role="staff",
            actor_name_fa="ک",
            actor_name_en="W",
            action="auth_login",
        )
        worker.delete()
        assert not AccessToken.objects.filter(key_hash="a" * 64).exists()
        entry = AuditLog.objects.get()
        assert entry.actor_id is None
        assert entry.actor_name_en == "W"


class TestRequests:
    def test_a_valid_row_is_accepted(self) -> None:
        request_row()

    @pytest.mark.parametrize("code", ["123", "abcdefghij", "123456789a", ""])
    def test_a_tracking_code_is_ten_digits(self, code: str) -> None:
        with violates("request_tracking_code_format"):
            request_row(tracking_code=code)

    def test_tracking_codes_are_unique(self) -> None:
        existing = ServiceRequest.objects.get(pk=REQ.loan_pending).tracking_code
        with violates("request_tracking_code_unique"):
            request_row(tracking_code=existing)

    def test_the_status_and_department_must_be_known(self) -> None:
        with violates("request_status_known"):
            request_row(status="teleported")
        with violates("request_department_known"):
            request_row(department="space_travel")

    @pytest.mark.parametrize("description", ["short", "x" * 9, "x" * 1001, ""])
    def test_the_description_length_is_bounded(self, description: str) -> None:
        with violates("request_description_length"):
            request_row(description=description)

    def test_the_description_bounds_are_inclusive_and_count_characters(self) -> None:
        request_row(description="x" * 10)
        request_row(description="x" * 1000)
        request_row(description="ن" * 10)  # 10 characters, 20 bytes

    @pytest.mark.parametrize("details", [[], "text", 5, [{"a": 1}]])
    def test_details_must_be_a_json_object(self, details: Any) -> None:
        with violates("request_details_is_object"):
            request_row(details=details)

    def test_details_cannot_be_null_either(self) -> None:
        with pytest.raises(IntegrityError), transaction.atomic():
            request_row(details=None)

    def test_a_tracking_code_longer_than_ten_characters_is_refused(self) -> None:
        with pytest.raises(DataError), transaction.atomic():
            request_row(tracking_code="12345678901")

    def test_the_applicant_snapshot_must_be_well_formed(self) -> None:
        with violates("request_customer_snapshot_format"):
            request_row(customer_national_id="123")
        with violates("request_customer_snapshot_format"):
            request_row(customer_phone="123")

    def test_the_service_must_exist(self) -> None:
        def insert_and_check() -> None:
            request_row(service_id="no-such-service")
            connection.check_constraints()  # the foreign key is deferred: checked here

        with pytest.raises(IntegrityError), transaction.atomic():
            insert_and_check()

    def test_a_service_with_requests_cannot_be_deleted(self) -> None:
        with pytest.raises(ProtectedError):
            Service.objects.get(pk="personal-loan").delete()

    def test_deleting_a_request_takes_its_timeline_with_it(self) -> None:
        assert TimelineEvent.objects.filter(request__id=REQ.loan_in_progress).exists()
        ServiceRequest.objects.filter(pk=REQ.loan_in_progress).delete()
        assert not TimelineEvent.objects.filter(request__id=REQ.loan_in_progress).exists()


class TestTimeline:
    def test_valid_events_of_every_kind_are_accepted(self) -> None:
        event_row(sequence=50)
        event_row(sequence=51, kind="submitted", visibility=None, body=None)
        event_row(
            sequence=52,
            kind="status_changed",
            from_status="pending_review",
            to_status="in_progress",
            visibility=None,
            body=None,
        )
        event_row(sequence=53, kind="assigned", visibility=None, body=None)  # "unassigned"
        event_row(
            sequence=54,
            kind="assigned",
            visibility=None,
            body=None,
            assignee_id=uid("u-reza"),
            assignee_role="staff",
            assignee_name_fa="رضا",
            assignee_name_en="Reza",
        )

    def test_a_sequence_number_is_used_once_per_request(self) -> None:
        with violates("timeline_request_sequence_unique"):
            event_row(request_id=REQ.loan_in_progress, sequence=0)
        event_row(request_id=REQ.loan_pending, sequence=7)  # another request may reuse numbers
        event_row(request_id=REQ.loan_in_progress, sequence=7)

    def test_the_kind_must_be_known(self) -> None:
        with violates("timeline_kind_known"):
            event_row(kind="weird")

    @pytest.mark.parametrize(
        "columns",
        [
            {"kind": "message", "body": None},  # a message needs its text
            {"kind": "message", "visibility": None},
            {"kind": "message", "body": ""},
            {"kind": "message", "body": "x" * 1001},
            {"kind": "message", "from_status": "pending_review"},  # ...and nothing else
            {"kind": "submitted"},  # a submission carries no message
            {
                "kind": "status_changed",
                "visibility": None,
                "body": None,
                "from_status": "pending_review",
                "to_status": "pending_review",
            },  # a change must change something
            {
                "kind": "status_changed",
                "visibility": None,
                "body": None,
                "from_status": "pending_review",
            },
            {"kind": "status_changed", "visibility": None, "body": None},
            {
                "kind": "assigned",
                "visibility": None,
                "body": None,
                "assignee_id": uid("u-reza"),
            },  # an assignee without its snapshot
            {
                "kind": "assigned",
                "visibility": None,
                "body": None,
                "assignee_role": "staff",
            },  # a snapshot without its assignee
            {"kind": "assigned", "from_status": "pending_review", "visibility": None, "body": None},
        ],
    )
    def test_each_kind_fills_exactly_its_own_columns(self, columns: dict[str, Any]) -> None:
        with violates("timeline_shape_matches_kind"):
            event_row(**columns)

    def test_the_message_length_bounds_are_inclusive(self) -> None:
        event_row(sequence=60, body="x")
        event_row(sequence=61, body="x" * 1000)


class TestAuditAndTokensAndServices:
    def test_the_audit_action_must_be_known(self) -> None:
        with violates("audit_action_known"):
            AuditLog.objects.create(action="something_else")

    def test_an_actor_snapshot_is_all_or_nothing(self) -> None:
        AuditLog.objects.create(action="auth_login")  # none
        AuditLog.objects.create(
            action="auth_login", actor_role="staff", actor_name_fa="ک", actor_name_en="W"
        )
        with violates("audit_actor_snapshot_complete"):
            AuditLog.objects.create(action="auth_login", actor_role="staff")
        with violates("audit_actor_snapshot_complete"):
            AuditLog.objects.create(action="auth_login", actor_name_en="W")

    def test_token_hashes_are_64_lower_case_hex_and_unique(self) -> None:
        owner = User.objects.get(pk=uid("u-reza"))
        later = timezone.now() + timedelta(hours=1)
        for bad in ("abc", "A" * 64, "g" * 64, "a" * 63):
            with violates("access_token_key_hash_format"):
                AccessToken.objects.create(user=owner, key_hash=bad, expires_at=later)
        with pytest.raises(DataError), transaction.atomic():
            AccessToken.objects.create(user=owner, key_hash="a" * 65, expires_at=later)
        AccessToken.objects.create(user=owner, key_hash="b" * 64, expires_at=later)
        with violates("access_token_key_hash_unique"):
            AccessToken.objects.create(user=owner, key_hash="b" * 64, expires_at=later)

    def test_a_token_cannot_expire_before_it_was_created(self) -> None:
        owner = User.objects.get(pk=uid("u-reza"))
        now = timezone.now()
        with violates("access_token_expires_after_creation"):
            AccessToken.objects.create(
                user=owner, key_hash="c" * 64, created_at=now, expires_at=now
            )

    def test_a_service_must_be_localised_positive_and_in_a_known_department(self) -> None:
        good: dict[str, Any] = {
            "id": "extra-service",
            "department": "loan",
            "title": {"fa": "الف", "en": "A"},
            "summary": {"fa": "الف", "en": "A"},
            "description": {"fa": "الف", "en": "A"},
            "eta_days": 3,
        }
        Service.objects.create(**good)
        with violates("service_department_known"):
            Service.objects.create(**{**good, "id": "s2", "department": "space"})
        with violates("service_eta_positive"):
            Service.objects.create(**{**good, "id": "s3", "eta_days": 0})
        with violates("service_texts_localized"):
            Service.objects.create(**{**good, "id": "s4", "title": {"fa": "الف"}})
        with violates("service_texts_localized"):
            Service.objects.create(**{**good, "id": "s5", "summary": ["x"]})
        with violates("service_lists_are_arrays"):
            Service.objects.create(**{**good, "id": "s6", "field_definitions": {"a": 1}})
        with violates("service_lists_are_arrays"):
            Service.objects.create(**{**good, "id": "s7", "requirements": "none"})


class TestIndexesAndExtensions:
    EXPECTED = {
        "users_user": {"user_department_ids_gin", "user_role_created_idx"},
        "users_accesstoken": {"access_token_user_live_idx", "access_token_expires_idx"},
        "catalog_service": {"service_department_pos_idx"},
        "requests_servicerequest": {
            "request_queue_idx",
            "request_assignee_status_idx",
            "request_customer_idx",
            "request_updated_idx",
            "request_code_trgm",
            "request_natid_trgm",
            "request_phone_trgm",
            "request_name_trgm",
        },
        "audit_auditlog": {"audit_actor_recent_idx", "audit_action_recent_idx"},
    }

    def indexes(self, table: str) -> set[str]:
        with connection.cursor() as cursor:
            cursor.execute("SELECT indexname FROM pg_indexes WHERE tablename = %s", [table])
            return {row[0] for row in cursor.fetchall()}

    @pytest.mark.parametrize("table", sorted(EXPECTED))
    def test_the_designed_indexes_exist(self, table: str) -> None:
        assert self.EXPECTED[table] <= self.indexes(table)

    def test_foreign_keys_that_a_composite_index_already_covers_have_no_second_index(self) -> None:
        names = self.indexes("requests_servicerequest")
        assert not any(name.startswith("requests_servicerequest_customer_id") for name in names)
        assert not any(name.startswith("requests_servicerequest_assignee_id") for name in names)
        assert not any(
            name.startswith("requests_timelineevent_request_id")
            for name in self.indexes("requests_timelineevent")
        )

    def test_the_trigram_extension_is_installed(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            assert cursor.fetchone() is not None

    def test_the_search_box_can_use_the_trigram_indexes(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute(
                "EXPLAIN SELECT id FROM requests_servicerequest WHERE customer_full_name ILIKE %s",
                ["%hossein%"],
            )
            plan = "\n".join(row[0] for row in cursor.fetchall())
        assert "request_name_trgm" in plan, plan

    def test_a_tracking_code_lookup_uses_its_unique_index(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
            cursor.execute(
                "EXPLAIN SELECT id FROM requests_servicerequest WHERE tracking_code = %s",
                ["4821093657"],
            )
            plan = "\n".join(row[0] for row in cursor.fetchall())
        assert "request_tracking_code_unique" in plan, plan


def test_uuid_helper_ids_are_valid_uuids() -> None:
    assert uuid.UUID(uid("u-reza")) == User.objects.get(username="reza").pk
