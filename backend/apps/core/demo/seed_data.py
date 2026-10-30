"""The demo's starting data (a port of the frontend's ``src/lib/store/seed.ts``).

Plain data only; ``apps.core.demo.service`` turns it into rows. Identifiers are *deterministic*
(UUIDv5 of the frontend's mock id), so the same account or request has the same id in every
database and after every reset, which makes the demo reproducible and the tests readable.

Everything here is invented sample data. The national IDs are well-formed (they pass the public
check-digit rule) but are not claimed to belong to anyone.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

#: Every seeded account uses this password; the login pages say so. It is a *public* demo secret.
DEMO_PASSWORD: Final = "Demo@1234"

_NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "urn:citizen-services-demo:seed")


def seed_id(key: str) -> uuid.UUID:
    """The stable id of a seeded record, e.g. ``seed_id("u-reza")`` or ``seed_id("req-seed-1")``."""
    return uuid.uuid5(_NAMESPACE, key)


def parse_instant(value: str) -> datetime:
    """``2026-10-05T08:30:00.000Z`` → an aware UTC datetime."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


CREATED_AT: Final = parse_instant("2026-09-01T08:00:00.000Z")


@dataclass(frozen=True, slots=True)
class SeedUser:
    #: The frontend's mock id (``u-reza``); the real primary key is ``seed_id(key)``.
    key: str
    role: Literal["customer", "staff", "admin"]
    # staff and administrators
    username: str | None = None
    name_fa: str | None = None
    name_en: str | None = None
    department_ids: tuple[str, ...] = ()
    # customers
    full_name: str | None = None
    national_id: str | None = None
    phone: str | None = None
    postal_code: str | None = None
    address: str | None = None

    @property
    def id(self) -> uuid.UUID:
        return seed_id(self.key)


SEED_USERS: Final[tuple[SeedUser, ...]] = (
    SeedUser(
        key="u-admin",
        role="admin",
        username="admin",
        name_fa="مدیر سامانه",
        name_en="System Administrator",
    ),
    SeedUser(
        key="u-reza",
        role="staff",
        username="reza",
        name_fa="رضا کریمی",
        name_en="Reza Karimi",
        department_ids=("loan",),
    ),
    SeedUser(
        key="u-sara",
        role="staff",
        username="sara",
        name_fa="سارا محمدی",
        name_en="Sara Mohammadi",
        department_ids=("raw_material",),
    ),
    SeedUser(
        key="u-ali",
        role="staff",
        username="ali",
        name_fa="علی رضایی",
        name_en="Ali Rezaei",
        department_ids=("vehicle",),
    ),
    SeedUser(
        key="u-maryam",
        role="staff",
        username="maryam",
        name_fa="مریم حسینی",
        name_en="Maryam Hosseini",
        department_ids=("housing",),
    ),
    SeedUser(
        key="c-amir",
        role="customer",
        full_name="امیر حسینی",
        national_id="0045813922",
        phone="09121234567",
        postal_code="1458943671",
        address="تهران، خیابان ولیعصر، پلاک ۱۲",
    ),
    SeedUser(
        key="c-maryam",
        role="customer",
        full_name="مریم احمدی",
        national_id="1277348561",
        phone="09352345678",
        postal_code="5166734829",
        address="تبریز، خیابان شریعتی، پلاک ۷",
    ),
    SeedUser(
        key="c-hossein",
        role="customer",
        full_name="Hossein Karimi",
        national_id="0592846717",
        phone="09189876543",
        postal_code="6134598217",
        address="Isfahan, Naqsh-e Jahan Square, No. 3",
    ),
)

SEED_USER_IDS: Final[frozenset[uuid.UUID]] = frozenset(user.id for user in SEED_USERS)
SEED_USERNAMES: Final[frozenset[str]] = frozenset(
    user.username for user in SEED_USERS if user.username
)


# --- Requests: each reads as a short story --------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeedStep:
    """One thing that happened to a request after it was filed."""

    kind: Literal["status", "assign", "message"]
    at: str
    #: Key of the user who did it.
    by: str
    #: ``status``: the new status. ``assign``: the assignee's key (``None`` = released).
    to: str | None = None
    visibility: Literal["public", "internal"] = "public"
    body: str = ""


@dataclass(frozen=True, slots=True)
class SeedRequest:
    key: str
    tracking_code: str
    customer: str
    service_id: str
    department: str
    description: str
    details: dict[str, Any]
    submitted_at: str
    steps: tuple[SeedStep, ...] = ()

    @property
    def id(self) -> uuid.UUID:
        return seed_id(self.key)


def _status(to: str, at: str, by: str) -> SeedStep:
    return SeedStep(kind="status", to=to, at=at, by=by)


def _assign(to: str | None, at: str, by: str) -> SeedStep:
    return SeedStep(kind="assign", to=to, at=at, by=by)


def _message(body: str, at: str, by: str, visibility: Literal["public", "internal"]) -> SeedStep:
    return SeedStep(kind="message", body=body, at=at, by=by, visibility=visibility)


SEED_REQUESTS: Final[tuple[SeedRequest, ...]] = (
    SeedRequest(
        key="req-seed-1",
        tracking_code="4821093657",
        customer="c-amir",
        service_id="personal-loan",
        department="loan",
        description="درخواست وام برای خرید لوازم منزل با اقساط ماهانه.",
        details={"amount": 150_000_000, "termMonths": "24", "purpose": "خرید لوازم منزل"},
        submitted_at="2026-10-05T08:30:00.000Z",
        steps=(
            _assign("u-reza", "2026-10-05T09:10:00.000Z", "u-reza"),
            _status("in_progress", "2026-10-05T09:12:00.000Z", "u-reza"),
            _message(
                "مدارک شما دریافت شد و در حال بررسی است. / "
                "Your documents were received and are under review.",
                "2026-10-05T09:20:00.000Z",
                "u-reza",
                "public",
            ),
        ),
    ),
    SeedRequest(
        key="req-seed-2",
        tracking_code="7093845216",
        customer="c-amir",
        service_id="vehicle-purchase",
        department="vehicle",
        description="به‌دنبال یک خودروی هیبریدی برای استفاده روزانه در شهر هستم.",
        details={"vehicleType": "sedan", "fuelType": "hybrid"},
        submitted_at="2026-10-11T14:05:00.000Z",
    ),
    SeedRequest(
        key="req-seed-3",
        tracking_code="3647182905",
        customer="c-maryam",
        service_id="steel-supply",
        department="raw_material",
        description="میلگرد برای پروژه ساختمانی در تبریز، تحویل در سه مرحله.",
        details={"material": "rebar", "quantity": 40, "deliveryCity": "تبریز"},
        submitted_at="2026-10-02T10:00:00.000Z",
        steps=(
            _assign("u-sara", "2026-10-02T11:00:00.000Z", "u-sara"),
            _status("in_progress", "2026-10-02T11:05:00.000Z", "u-sara"),
            _message(
                "لطفاً شماره پروژه را اعلام کنید. / Please share the project number.",
                "2026-10-03T08:40:00.000Z",
                "u-sara",
                "public",
            ),
            _status("needs_correction", "2026-10-03T08:41:00.000Z", "u-sara"),
        ),
    ),
    SeedRequest(
        key="req-seed-4",
        tracking_code="1059382746",
        customer="c-maryam",
        service_id="housing-unit",
        department="housing",
        description="خانوار چهارنفره هستیم و یک آپارتمان در تبریز نیاز داریم.",
        details={"unitType": "apartment", "householdSize": 4, "preferredCity": "تبریز"},
        submitted_at="2026-09-20T09:15:00.000Z",
        steps=(
            _assign("u-maryam", "2026-09-20T10:00:00.000Z", "u-maryam"),
            _status("in_progress", "2026-09-20T10:05:00.000Z", "u-maryam"),
            _message(
                "Eligibility checked against the household register — looks fine.",
                "2026-09-27T12:00:00.000Z",
                "u-maryam",
                "internal",
            ),
            _status("approved", "2026-09-28T12:30:00.000Z", "u-maryam"),
        ),
    ),
    SeedRequest(
        key="req-seed-5",
        tracking_code="8273641950",
        customer="c-hossein",
        service_id="business-loan",
        department="loan",
        description="Working capital to buy a second corrugator for our packaging workshop.",
        details={
            "amount": 800_000_000,
            "termMonths": "36",
            "businessField": "Packaging manufacturing",
        },
        submitted_at="2026-10-12T07:45:00.000Z",
    ),
    SeedRequest(
        key="req-seed-6",
        tracking_code="2916485073",
        customer="c-hossein",
        service_id="packaging-supply",
        department="raw_material",
        description="Monthly cardboard stock for the workshop.",
        details={"material": "cardboard", "quantity": 5000, "deliveryCity": "Isfahan"},
        submitted_at="2026-09-10T08:00:00.000Z",
        steps=(
            _assign("u-sara", "2026-09-10T09:00:00.000Z", "u-sara"),
            _status("in_progress", "2026-09-10T09:02:00.000Z", "u-sara"),
            _status("approved", "2026-09-12T10:00:00.000Z", "u-sara"),
            _status("closed", "2026-09-20T10:00:00.000Z", "u-sara"),
        ),
    ),
    SeedRequest(
        key="req-seed-7",
        tracking_code="6350174829",
        customer="c-amir",
        service_id="rent-subsidy",
        department="housing",
        description="اجاره ماهانه خانه ما امسال افزایش یافته است.",
        details={"monthlyRent": 12_000_000, "householdSize": 3},
        submitted_at="2026-10-08T16:20:00.000Z",
        steps=(
            _assign("u-maryam", "2026-10-09T08:00:00.000Z", "u-maryam"),
            _status("in_progress", "2026-10-09T08:03:00.000Z", "u-maryam"),
        ),
    ),
    SeedRequest(
        key="req-seed-8",
        tracking_code="5184730962",
        customer="c-hossein",
        service_id="vehicle-maintenance",
        department="vehicle",
        description="Periodic service for the delivery van.",
        details={"plate": "12B34567", "serviceType": "periodic"},
        submitted_at="2026-10-06T11:10:00.000Z",
        steps=(
            _assign("u-ali", "2026-10-06T12:00:00.000Z", "u-ali"),
            _status("in_progress", "2026-10-06T12:02:00.000Z", "u-ali"),
            _message(
                "ظرفیت این ماه تکمیل است. / Service slots are full this month.",
                "2026-10-07T09:00:00.000Z",
                "u-ali",
                "public",
            ),
            _status("rejected", "2026-10-07T09:01:00.000Z", "u-ali"),
        ),
    ),
)
