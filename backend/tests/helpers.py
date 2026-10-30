"""Shared test helpers: a tiny API client and the seeded ids (the twin of ``tests/helpers.ts``)."""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from rest_framework.test import APIClient

from apps.core.demo.seed_data import DEMO_PASSWORD, seed_id

__all__ = [
    "DEMO_PASSWORD",
    "NATIONAL_IDS",
    "REQ",
    "STATUS_OF_CODE",
    "Api",
    "Reply",
    "customer_api",
    "expect_error",
    "staff_api",
    "uid",
    "valid_loan",
    "with_check_digit",
]

NATIONAL_IDS: Final = {"amir": "0045813922", "maryam": "1277348561", "hossein": "0592846717"}

#: HTTP status that goes with each machine-readable error code.
STATUS_OF_CODE: Final = {
    "unauthenticated": 401,
    "invalid_credentials": 401,
    "forbidden": 403,
    "not_found": 404,
    "validation": 400,
    "national_id_taken": 409,
    "phone_taken": 409,
    "username_taken": 409,
    "service_unavailable": 409,
    "invalid_transition": 409,
    "request_closed": 409,
    "network": 429,
}


def uid(key: str) -> str:
    """The id of a seeded record by its frontend key, e.g. ``uid("u-reza")``."""
    return str(seed_id(key))


class REQ:
    """Seeded requests, by department (see ``apps.core.demo.seed_data``)."""

    loan_in_progress = uid("req-seed-1")  # amir, assigned to reza
    vehicle_pending = uid("req-seed-2")  # amir
    raw_needs_correction = uid("req-seed-3")  # maryam, assigned to sara
    housing_approved = uid("req-seed-4")  # maryam, has an INTERNAL note
    loan_pending = uid("req-seed-5")  # hossein, unassigned
    raw_closed = uid("req-seed-6")  # hossein
    housing_in_progress = uid("req-seed-7")  # amir
    vehicle_rejected = uid("req-seed-8")  # hossein


valid_loan: Final[dict[str, Any]] = {
    "serviceId": "personal-loan",
    "description": "I need a loan to pay for wedding costs.",
    "details": {"amount": 100_000_000, "termMonths": "12", "purpose": "Wedding"},
}


def with_check_digit(prefix: str) -> str:
    """A checksum-valid national ID from a 9-digit prefix (independent of the code under test)."""
    total = sum(int(digit) * (10 - index) for index, digit in enumerate(prefix))
    remainder = total % 11
    return f"{prefix}{remainder if remainder < 2 else 11 - remainder}"


def random_valid_national_id(rng: random.Random) -> str:
    return with_check_digit(f"{rng.randrange(10**9):09d}")


@dataclass(frozen=True)
class Reply:
    status: int
    data: Any
    headers: Mapping[str, str]

    @property
    def code(self) -> str | None:
        return self.data.get("code") if isinstance(self.data, dict) else None


class Api:
    """DRF's test client, with an optional bearer token and ``Accept-Language``."""

    def __init__(
        self,
        token: str | None = None,
        *,
        user: dict[str, Any] | None = None,
        language: str | None = None,
        raise_server_errors: bool = True,
    ) -> None:
        self.client = APIClient()
        # ``False`` lets a test look at the 500 response a real client would get.
        self.client.raise_request_exception = raise_server_errors
        self.token = token
        self.user = user or {}
        self.language = language

    def _headers(self, extra: Mapping[str, str]) -> dict[str, str]:
        headers = dict(extra)
        if self.token is not None:
            headers.setdefault("HTTP_AUTHORIZATION", f"Bearer {self.token}")
        if self.language is not None:
            headers.setdefault("HTTP_ACCEPT_LANGUAGE", self.language)
        return headers

    def call(
        self, method: str, path: str, body: Any = None, *, raw: bytes | None = None, **extra: str
    ) -> Reply:
        return self._send(method, path, body, raw, extra)

    def _send(
        self, method: str, path: str, body: Any, raw: bytes | None, extra: Mapping[str, str]
    ) -> Reply:
        send = getattr(self.client, method)
        headers = self._headers(extra)
        if raw is not None:
            response = send(path, data=raw, content_type="application/json", **headers)
        elif method == "get":
            response = send(path, data=body, **headers)
        else:
            response = send(path, data=body, format="json", **headers)
        content = response.content
        data = response.json() if content and "json" in response.get("Content-Type", "") else None
        return Reply(response.status_code, data, dict(response.items()))

    def get(self, path: str, params: Mapping[str, Any] | None = None, **extra: str) -> Reply:
        return self._send("get", path, dict(params) if params else None, None, extra)

    def post(self, path: str, body: Any = None, **extra: str) -> Reply:
        return self._send("post", path, {} if body is None else body, None, extra)

    def patch(self, path: str, body: Any = None, **extra: str) -> Reply:
        return self._send("patch", path, {} if body is None else body, None, extra)

    # --- the endpoints, by the names the frontend's API layer uses ---------------------------

    def me(self) -> Reply:
        return self.get("/api/auth/me/")

    def queue(self, **params: Any) -> Reply:
        return self.get("/api/requests/queue/", params)

    def mine(self) -> Reply:
        return self.get("/api/requests/mine/")

    def request(self, request_id: str) -> Reply:
        return self.get(f"/api/requests/{request_id}/")

    def create(self, body: Any) -> Reply:
        return self.post("/api/requests/", body)

    def transition(self, request_id: str, to: str, note: str | None = None) -> Reply:
        body: dict[str, Any] = {"to": to}
        if note is not None:
            body["note"] = note
        return self.post(f"/api/requests/{request_id}/transition/", body)

    def assign(self, request_id: str, assignee_id: str | None) -> Reply:
        return self.post(f"/api/requests/{request_id}/assign/", {"assigneeId": assignee_id})

    def message(self, request_id: str, body: str, visibility: str = "public") -> Reply:
        return self.post(
            f"/api/requests/{request_id}/messages/", {"body": body, "visibility": visibility}
        )

    def assignable(self, department_id: str) -> Reply:
        return self.get("/api/requests/assignable-staff/", {"departmentId": department_id})

    def audit(self, **params: Any) -> Reply:
        return self.get("/api/audit/", params)


def staff_api(username: str, password: str = DEMO_PASSWORD, **options: Any) -> Api:
    reply = Api().post("/api/auth/login/staff/", {"username": username, "password": password})
    assert reply.status == 200, reply.data
    return Api(reply.data["token"], user=reply.data["user"], **options)


def customer_api(who: str, password: str = DEMO_PASSWORD, **options: Any) -> Api:
    reply = Api().post(
        "/api/auth/login/customer/", {"nationalId": NATIONAL_IDS[who], "password": password}
    )
    assert reply.status == 200, reply.data
    return Api(reply.data["token"], user=reply.data["user"], **options)


def expect_error(reply: Reply, code: str, *, status: int | None = None) -> None:
    """The reply is a contract error with ``code`` (and its natural HTTP status)."""
    assert isinstance(reply.data, dict), reply
    assert reply.data.get("code") == code, reply.data
    assert reply.status == (status or STATUS_OF_CODE[code]), (reply.status, reply.data)
    assert set(reply.data) == {"code", "detail", "errors"}, reply.data
    assert isinstance(reply.data["detail"], str)
    assert reply.data["detail"]
    assert isinstance(reply.data["errors"], dict)
