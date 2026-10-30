"""The error contract, transport-level behaviour and response headers."""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.db import OperationalError

from apps.core import messages as m
from apps.core.exceptions import ApiErrorCode, flatten_validation_errors
from tests.helpers import (
    DEMO_PASSWORD,
    REQ,
    Api,
    customer_api,
    expect_error,
    staff_api,
    valid_loan,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]

LOGIN = "/api/auth/login/staff/"


class TestEveryErrorHasTheSameShape:
    def test_a_sample_of_every_code(self) -> None:
        samples = {
            "unauthenticated": Api().me(),
            "forbidden": staff_api("reza").get("/api/staff/"),
            "not_found": customer_api("amir").request("nope"),
            "validation": Api().post(LOGIN, {}),
            "invalid_credentials": Api().post(LOGIN, {"username": "x", "password": "y"}),
            "national_id_taken": Api().post(
                "/api/auth/register/",
                {
                    "fullName": "Nima Ahmadi",
                    "nationalId": "0045813922",
                    "phone": "09151112233",
                    "postalCode": "1234567890",
                    "address": "Mashhad, Sajjad Blvd, No. 4",
                    "password": "Strong1pass",
                },
            ),
            "invalid_transition": staff_api("reza").transition(REQ.loan_pending, "approved"),
            "request_closed": staff_api("sara").transition(REQ.raw_closed, "in_progress"),
        }
        for code, reply in samples.items():
            expect_error(reply, code)
            assert reply.headers["Content-Type"].startswith("application/json")

    def test_only_documented_codes_exist(self) -> None:
        assert {code.value for code in ApiErrorCode} == {
            "unauthenticated",
            "forbidden",
            "not_found",
            "validation",
            "invalid_credentials",
            "national_id_taken",
            "phone_taken",
            "username_taken",
            "service_unavailable",
            "invalid_transition",
            "request_closed",
            "network",
        }

    def test_every_code_has_text_in_both_languages(self) -> None:
        for code in ApiErrorCode:
            for language in m.SUPPORTED_LANGUAGES:
                assert m.ERRORS[language][code.value].strip()
        assert m.ERRORS["en"].keys() == m.ERRORS["fa"].keys()

    def test_401_carries_a_www_authenticate_challenge(self) -> None:
        assert Api().me().headers["WWW-Authenticate"] == 'Bearer realm="api"'
        assert (
            Api()
            .post(LOGIN, {"username": "x", "password": "y"})
            .headers["WWW-Authenticate"]
            .startswith("Bearer")
        )

    def test_field_messages_are_always_known_dictionary_keys(self) -> None:
        bodies: list[tuple[str, Any]] = [
            (LOGIN, {}),
            (LOGIN, {"username": 5, "password": ["x"]}),
            ("/api/auth/register/", {}),
            (
                "/api/auth/register/",
                {"fullName": 1, "nationalId": {}, "phone": [], "password": None},
            ),
        ]
        for path, body in bodies:
            reply = Api().post(path, body)
            assert reply.status == 400
            for messages in reply.data["errors"].values():
                assert set(messages) <= m.VALIDATION_KEYS, (path, body, messages)
        admin = staff_api("admin")
        for body in ({}, {"nameFa": 1, "departmentIds": [{}], "username": None}):
            reply = admin.post("/api/staff/", body)
            for messages in reply.data["errors"].values():
                assert set(messages) <= m.VALIDATION_KEYS
        reply = customer_api("amir").create(
            {**valid_loan, "details": {"amount": [1], "termMonths": {}}}
        )
        for messages in reply.data["errors"].values():
            assert set(messages) <= m.VALIDATION_KEYS

    def test_backend_only_keys_are_a_small_documented_set(self) -> None:
        assert {"validation.invalid", "validation.password.max"} == m.BACKEND_ONLY_KEYS
        assert m.BACKEND_ONLY_KEYS <= m.VALIDATION_KEYS


class TestFlattening:
    def test_nested_errors_become_dotted_paths(self) -> None:
        flat = flatten_validation_errors(
            {
                "details": {"amount": ["validation.number.min"]},
                "description": ["validation.required"],
            }
        )
        assert flat == {
            "details.amount": ["validation.number.min"],
            "description": ["validation.required"],
        }

    def test_lists_of_child_errors_are_indexed(self) -> None:
        flat = flatten_validation_errors({"items": [{}, {"name": ["validation.required"]}]})
        assert flat == {"items.1.name": ["validation.required"]}

    def test_root_level_problems_are_non_field_errors(self) -> None:
        assert flatten_validation_errors(["validation.required"]) == {
            "non_field_errors": ["validation.required"]
        }
        assert flatten_validation_errors("validation.required") == {
            "non_field_errors": ["validation.required"]
        }

    def test_anything_that_is_not_a_known_key_becomes_the_generic_fallback(self) -> None:
        flat = flatten_validation_errors(
            {"name": ["This field may not be blank.", "validation.required"]}
        )
        assert flat == {"name": ["validation.invalid", "validation.required"]}

    def test_duplicates_are_dropped(self) -> None:
        assert flatten_validation_errors({"a": ["validation.required", "validation.required"]}) == {
            "a": ["validation.required"]
        }


class TestLanguage:
    @pytest.mark.parametrize(
        ("header", "language"),
        [
            (None, "en"),
            ("", "en"),
            ("en", "en"),
            ("fa", "fa"),
            ("FA", "fa"),
            ("fa-IR", "fa"),
            ("fa-IR,fa;q=0.9,en;q=0.8", "fa"),
            ("en-US,en;q=0.9,fa;q=0.8", "en"),
            ("en;q=0.5, fa;q=0.9", "fa"),
            ("fa;q=0, en;q=0.1", "en"),
            ("de, fr;q=0.9", "en"),
            ("*", "en"),
            ("fa;q=abc", "en"),
            (";;;,,,", "en"),
            ("fa;q=0.5,en;q=0.5", "fa"),  # a tie goes to the first listed
        ],
    )
    def test_accept_language_picks_the_detail_text(self, header: str | None, language: str) -> None:
        extra = {"HTTP_ACCEPT_LANGUAGE": header} if header is not None else {}
        reply = Api().get("/api/auth/me/", None, **extra)
        assert reply.data["detail"] == m.ERRORS[language]["unauthenticated"]  # type: ignore[index]
        assert reply.data["code"] == "unauthenticated"  # the code never depends on language

    def test_the_persian_sentence_is_really_persian(self) -> None:
        reply = Api(language="fa").me()
        assert "نشست" in reply.data["detail"]

    def test_field_keys_do_not_depend_on_language(self) -> None:
        en = Api(language="en").post(LOGIN, {})
        fa = Api(language="fa").post(LOGIN, {})
        assert en.data["errors"] == fa.data["errors"]
        assert en.data["detail"] != fa.data["detail"]


class TestMalformedInput:
    def test_unknown_routes_are_json_404s(self) -> None:
        for path in ("/api/nope/", "/nope", "/api/auth/me", "/api/requests//", "/"):
            reply = Api().get(path)
            expect_error(reply, "not_found")

    def test_a_wrong_method_is_a_405_with_the_contracts_not_found_code(self) -> None:
        reply = Api().get(LOGIN)
        expect_error(reply, "not_found", status=405)
        assert "POST" in reply.headers["Allow"]
        expect_error(Api().call("delete", "/api/catalog/services/"), "not_found", status=405)

    def test_a_missing_trailing_slash_is_not_redirected(self) -> None:
        reply = Api().post("/api/auth/login/staff", {"username": "reza", "password": DEMO_PASSWORD})
        expect_error(reply, "not_found")

    def test_an_unsupported_media_type_is_a_415(self) -> None:
        reply = Api().client.post(LOGIN, data="username=reza", content_type="text/plain")
        assert reply.status_code == 415
        assert reply.json()["code"] == "validation"

    @pytest.mark.parametrize("raw", [b"{bad", b"", b'{"username": "reza",}', b"\xff\xfe", b"nul"])
    def test_a_body_that_is_not_json_is_a_validation_error(self, raw: bytes) -> None:
        reply = Api().call("post", LOGIN, raw=raw)
        expect_error(reply, "validation")

    @pytest.mark.parametrize("raw", [b"[1, 2]", b'"text"', b"42", b"null", b"true"])
    def test_a_json_body_that_is_not_an_object_is_a_validation_error(self, raw: bytes) -> None:
        reply = Api().call("post", LOGIN, raw=raw)
        expect_error(reply, "validation")
        assert set(reply.data["errors"]) <= {"non_field_errors", "username", "password"}

    @pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity"])
    def test_non_finite_numbers_are_refused_at_the_parser(self, literal: bytes) -> None:
        raw = (
            b'{"serviceId":"personal-loan","description":"long enough text","details":{"amount":'
            + literal
            + b"}}"
        )
        expect_error(customer_api("amir").call("post", "/api/requests/", raw=raw), "validation")

    def test_a_huge_exponent_is_a_validation_error_not_a_crash(self) -> None:
        raw = (
            b'{"serviceId":"personal-loan","description":"long enough text",'
            b'"details":{"amount":1e999,"termMonths":"12","purpose":"x"}}'
        )
        reply = customer_api("amir").call("post", "/api/requests/", raw=raw)
        expect_error(reply, "validation")
        assert reply.data["errors"] == {"details.amount": ["validation.number.invalid"]}

    def test_a_very_large_integer_is_just_out_of_range(self) -> None:
        raw = (
            b'{"serviceId":"personal-loan","description":"long enough text",'
            b'"details":{"amount":' + b"9" * 400 + b',"termMonths":"12","purpose":"x"}}'
        )
        reply = customer_api("amir").call("post", "/api/requests/", raw=raw)
        expect_error(reply, "validation")
        assert reply.data["errors"] == {"details.amount": ["validation.number.max"]}

    def test_deeply_nested_json_is_a_client_error_not_a_crash(self) -> None:
        # Small enough to pass the size limit, deep enough to exhaust Python's recursion limit.
        raw = b'{"a":' + b"[" * 20_000 + b"]" * 20_000 + b"}"
        assert len(raw) < 64 * 1024
        reply = Api().call("post", LOGIN, raw=raw)
        expect_error(reply, "validation")

    def test_a_body_over_the_limit_is_refused_before_it_is_read(self) -> None:
        raw = b'{"username":"' + b"a" * (70 * 1024) + b'","password":"x"}'
        reply = Api().call("post", LOGIN, raw=raw)
        expect_error(reply, "validation", status=413)

    def test_a_negative_or_garbled_content_length_is_a_400(self) -> None:
        for value in ("-5", "abc"):
            reply = Api().client.post(
                LOGIN, data=b"{}", content_type="application/json", CONTENT_LENGTH=value
            )
            assert reply.status_code == 400
            assert reply.json()["code"] == "validation"

    def test_the_limit_is_generous_for_real_payloads(self) -> None:
        body = {**valid_loan, "description": "x" * 1000}
        assert customer_api("amir").create(body).status == 201

    def test_nul_bytes_and_lone_surrogates_in_text_are_validation_errors(self) -> None:
        for text in ("with\x00nul", "lone\ud800half"):
            payload = json.dumps(
                {
                    "fullName": text,
                    "nationalId": "1234567890",
                    "phone": "1",
                    "postalCode": "1",
                    "address": "x",
                    "password": "Strong1pass",
                },
                ensure_ascii=True,
            ).encode()
            reply = Api().call("post", "/api/auth/register/", raw=payload)
            expect_error(reply, "validation")
            assert reply.data["errors"]["fullName"] == ["validation.fullName"]

    def test_query_strings_with_nul_or_junk_are_validation_errors(self) -> None:
        admin = staff_api("admin")
        reply = admin.get("/api/requests/queue/", {"search": "a\x00b"})
        expect_error(reply, "validation")
        assert admin.get("/api/requests/queue/?page=1&page=2").status == 200  # last one wins

    def test_unicode_in_urls_is_not_found_not_a_crash(self) -> None:
        for path in ("/api/requests/ü/", "/api/catalog/services/%00/", "/api/requests/%ff/"):
            assert Api(staff_api("admin").token).get(path).status in (404,)


class TestUnexpectedFailures:
    def test_an_unexpected_exception_is_the_generic_network_error_and_logs_a_traceback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from apps.users.services import AuthService

        def boom(**kwargs: Any) -> None:
            raise RuntimeError("secret internal detail")

        monkeypatch.setattr(AuthService, "login_staff", staticmethod(boom))
        client = Api(raise_server_errors=False)
        with caplog.at_level("ERROR"):
            reply = client.post(LOGIN, {"username": "reza", "password": DEMO_PASSWORD})
        expect_error(reply, "network", status=500)
        assert "secret internal detail" not in json.dumps(reply.data)
        assert "X-Request-ID" in reply.headers
        assert any("secret internal detail" in str(record.exc_info) for record in caplog.records)

    def test_the_500_page_speaks_the_callers_language(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from apps.users.services import AuthService

        monkeypatch.setattr(AuthService, "login_staff", staticmethod(lambda **kwargs: 1 / 0))
        reply = Api(language="fa", raise_server_errors=False).post(
            LOGIN, {"username": "reza", "password": DEMO_PASSWORD}
        )
        assert reply.status == 500
        assert reply.data["detail"] == m.ERRORS["fa"]["network"]

    def test_a_failed_write_leaves_no_partial_state(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from apps.audit.models import AuditLog
        from apps.audit.services import AuditService
        from apps.requests.models import ServiceRequest, TimelineEvent

        def broken(**kwargs: Any) -> None:
            raise RuntimeError("audit store down")

        amir = customer_api("amir")
        amir.client.raise_request_exception = False
        before = (
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            AuditLog.objects.count(),
        )
        monkeypatch.setattr(AuditService, "record", staticmethod(broken))
        reply = amir.create(valid_loan)
        assert reply.status == 500
        monkeypatch.undo()
        assert before == (
            ServiceRequest.objects.count(),
            TimelineEvent.objects.count(),
            AuditLog.objects.count(),
        )


class TestRequestId:
    def test_every_response_carries_one(self) -> None:
        reply = Api().get("/health/")
        assert len(reply.headers["X-Request-ID"]) >= 8

    def test_a_sane_incoming_id_is_kept_and_echoed(self) -> None:
        reply = Api().get("/health/", HTTP_X_REQUEST_ID="trace-1234.abcd")
        assert reply.headers["X-Request-ID"] == "trace-1234.abcd"

    @pytest.mark.parametrize(
        "bad", ["short", "has spaces in it", "x" * 65, "bad;chars!!", "new\\nline1234"]
    )
    def test_an_unsafe_incoming_id_is_replaced(self, bad: str) -> None:
        reply = Api().get("/health/", HTTP_X_REQUEST_ID=bad)
        assert reply.headers["X-Request-ID"] != bad
        assert len(reply.headers["X-Request-ID"]) == 32

    def test_error_responses_carry_it_too(self) -> None:
        assert "X-Request-ID" in Api().me().headers
        assert "X-Request-ID" in Api().get("/nope").headers

    def test_ids_are_unique_per_request(self) -> None:
        first = Api().get("/health/").headers["X-Request-ID"]
        second = Api().get("/health/").headers["X-Request-ID"]
        assert first != second

    def test_the_log_filter_tags_records_with_the_id(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from apps.core.requestid import RequestIDLogFilter, reset_request_id, set_request_id

        token = set_request_id("abc-12345678")
        try:
            record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
            assert RequestIDLogFilter().filter(record)
            assert record.request_id == "abc-12345678"  # type: ignore[attr-defined]
        finally:
            reset_request_id(token)
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "msg", None, None)
        RequestIDLogFilter().filter(record)
        assert record.request_id == "-"  # type: ignore[attr-defined]


class TestHealth:
    def test_reports_ok_when_the_database_answers(self) -> None:
        reply = Api().get("/health/")
        assert reply.status == 200
        assert reply.data == {"status": "ok"}

    def test_needs_no_credentials_and_ignores_bad_ones(self) -> None:
        assert Api("0" * 64).get("/health/").status == 200

    def test_reports_unavailable_when_the_database_does_not(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Broken:
            def cursor(self) -> Any:
                raise OperationalError("connection refused")

        monkeypatch.setattr("apps.core.views.connection", Broken())
        reply = Api().get("/health/")
        assert reply.status == 503
        assert reply.data == {"status": "unavailable"}
        assert "refused" not in json.dumps(reply.data)

    def test_is_not_throttled(self) -> None:
        for _ in range(50):
            assert Api().get("/health/").status == 200


class TestHeadersAndCors:
    def test_security_headers_are_present(self) -> None:
        reply = Api().get("/api/catalog/services/")
        assert reply.headers["X-Content-Type-Options"] == "nosniff"
        assert reply.headers["X-Frame-Options"] == "DENY"
        assert reply.headers["Referrer-Policy"] == "same-origin"

    def test_a_preflight_from_an_allowed_origin_is_answered(self) -> None:
        reply = Api().client.options(
            LOGIN,
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization,content-type,accept-language",
        )
        assert reply.status_code == 200
        assert reply["Access-Control-Allow-Origin"] == "http://localhost:3000"
        allowed = reply["Access-Control-Allow-Headers"].lower()
        assert "authorization" in allowed
        assert "content-type" in allowed
        assert "accept-language" in allowed
        assert "x-request-id" in allowed
        assert "Access-Control-Allow-Credentials" not in reply

    def test_other_origins_get_no_cors_headers(self) -> None:
        reply = Api().client.get("/api/catalog/services/", HTTP_ORIGIN="https://evil.example")
        assert reply.status_code == 200
        assert "Access-Control-Allow-Origin" not in reply

    def test_the_headers_the_frontend_needs_are_exposed(self) -> None:
        reply = Api().client.get("/api/catalog/services/", HTTP_ORIGIN="http://localhost:3000")
        exposed = reply["Access-Control-Expose-Headers"]
        assert "Retry-After" in exposed
        assert "X-Request-ID" in exposed

    def test_cors_does_not_apply_outside_the_api(self) -> None:
        reply = Api().client.get("/health/", HTTP_ORIGIN="http://localhost:3000")
        assert "Access-Control-Allow-Origin" not in reply
