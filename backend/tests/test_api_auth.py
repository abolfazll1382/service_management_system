"""Sign-in, registration and sessions (port of the frontend's ``api.auth.test.ts`` plus the
server-only concerns: token storage, expiry, throttling)."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import timedelta
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from apps.audit.models import AuditLog
from apps.users.models import AccessToken, User
from tests.helpers import (
    DEMO_PASSWORD,
    NATIONAL_IDS,
    Api,
    customer_api,
    expect_error,
    staff_api,
    uid,
    with_check_digit,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("demo")]

CREDENTIAL_WORDS = re.compile(r"password|passwordHash|passwordSalt|key_hash", re.IGNORECASE)


def new_customer(**overrides: Any) -> dict[str, Any]:
    return {
        "fullName": "Nima Ahmadi",
        "nationalId": with_check_digit("123456789"),
        "phone": "09151112233",
        "postalCode": "1234567890",
        "address": "Mashhad, Sajjad Blvd, No. 4",
        "password": "Strong1pass",
        **overrides,
    }


def staff_login(username: str, password: str = DEMO_PASSWORD) -> Any:
    return Api().post("/api/auth/login/staff/", {"username": username, "password": password})


def customer_login(national_id: str, password: str = DEMO_PASSWORD) -> Any:
    return Api().post(
        "/api/auth/login/customer/", {"nationalId": national_id, "password": password}
    )


def age_token(token: str, *, expired: bool = False, revoked: bool = False) -> None:
    key_hash = hashlib.sha256(token.encode()).hexdigest()
    changes: dict[str, Any] = {}
    if expired:
        changes |= {
            "created_at": timezone.now() - timedelta(days=2),
            "expires_at": timezone.now() - timedelta(days=1),
        }
    if revoked:
        changes["revoked_at"] = timezone.now()
    assert AccessToken.objects.filter(key_hash=key_hash).update(**changes) == 1


class TestStaffSignIn:
    def test_returns_a_token_and_a_profile_without_credentials(self) -> None:
        reply = staff_login("reza")
        assert reply.status == 200
        assert re.fullmatch(r"[0-9a-f]{64}", reply.data["token"])
        assert reply.data["user"] == {
            "id": uid("u-reza"),
            "role": "staff",
            "isActive": True,
            "createdAt": "2026-09-01T08:00:00.000Z",
            "username": "reza",
            "name": {"fa": "رضا کریمی", "en": "Reza Karimi"},
            "departmentIds": ["loan"],
        }
        assert not CREDENTIAL_WORDS.search(json.dumps(reply.data["user"]))

    def test_the_administrator_signs_in_through_the_same_door(self) -> None:
        reply = staff_login("admin")
        assert reply.status == 200
        assert reply.data["user"]["role"] == "admin"
        assert "departmentIds" not in reply.data["user"]

    def test_ignores_case_and_surrounding_spaces_in_the_username(self) -> None:
        assert staff_login("  REZA ").status == 200
        assert staff_login("Reza").data["user"]["username"] == "reza"

    def test_a_wrong_password_and_an_unknown_user_are_answered_identically(self) -> None:
        wrong = staff_login("reza", "wrong-pass1")
        unknown = staff_login("nobody")
        expect_error(wrong, "invalid_credentials")
        expect_error(unknown, "invalid_credentials")
        assert wrong.data == unknown.data
        assert wrong.status == unknown.status == 401

    def test_a_deactivated_account_is_answered_like_a_wrong_password(self) -> None:
        User.objects.filter(username="reza").update(is_active=False)
        reply = staff_login("reza")
        expect_error(reply, "invalid_credentials")
        assert reply.data == staff_login("reza", "wrong-pass1").data

    def test_a_customer_cannot_sign_in_through_the_staff_door(self) -> None:
        expect_error(staff_login(NATIONAL_IDS["amir"]), "invalid_credentials")

    def test_an_empty_or_missing_field_is_a_validation_error_with_field_keys(self) -> None:
        reply = Api().post("/api/auth/login/staff/", {"username": "  ", "password": ""})
        expect_error(reply, "validation")
        assert reply.data["errors"] == {
            "username": ["validation.required"],
            "password": ["validation.required"],
        }
        assert Api().post("/api/auth/login/staff/", {}).data["errors"].keys() == {
            "username",
            "password",
        }

    def test_the_password_is_used_exactly_as_typed(self) -> None:
        assert staff_login("reza", DEMO_PASSWORD + " ").status == 401
        assert staff_login("reza", f" {DEMO_PASSWORD}").status == 401

    def test_each_sign_in_issues_a_new_independent_token(self) -> None:
        first = staff_login("reza").data["token"]
        second = staff_login("reza").data["token"]
        assert first != second
        assert Api(first).me().status == Api(second).me().status == 200


class TestCustomerSignIn:
    def test_signs_in_with_national_id_and_password(self) -> None:
        reply = customer_login(NATIONAL_IDS["amir"])
        assert reply.status == 200
        user = reply.data["user"]
        assert user == {
            "id": uid("c-amir"),
            "role": "customer",
            "isActive": True,
            "createdAt": "2026-09-01T08:00:00.000Z",
            "fullName": "امیر حسینی",
            "nationalId": NATIONAL_IDS["amir"],
            "phone": "09121234567",
            "postalCode": "1458943671",
            "address": "تهران، خیابان ولیعصر، پلاک ۱۲",
        }
        assert not CREDENTIAL_WORDS.search(json.dumps(user))

    def test_a_wrong_password_is_invalid_credentials(self) -> None:
        expect_error(customer_login(NATIONAL_IDS["amir"], "nope"), "invalid_credentials")

    def test_a_well_formed_id_with_a_bad_checksum_gets_the_same_generic_answer(self) -> None:
        # Shape only is checked at sign-in, so nothing hints at which part was wrong.
        wrong_checksum = customer_login("1234567890")
        expect_error(wrong_checksum, "invalid_credentials")
        assert wrong_checksum.data == customer_login(NATIONAL_IDS["amir"], "nope").data

    def test_an_unregistered_valid_id_gets_the_same_generic_answer(self) -> None:
        expect_error(customer_login(with_check_digit("987654321")), "invalid_credentials")

    @pytest.mark.parametrize("bad", ["123", "12345678901", "00458139a2", "", "0045813922 x"])
    def test_a_malformed_id_is_a_validation_error(self, bad: str) -> None:
        reply = customer_login(bad)
        expect_error(reply, "validation")
        assert "nationalId" in reply.data["errors"]
        assert set(reply.data["errors"]["nationalId"]) <= {
            "validation.nationalId.format",
            "validation.required",
        }

    def test_persian_digits_are_normalised_by_the_server(self) -> None:
        # Documented deviation: the frontend mock rejected these; the server accepts what the
        # form would have converted anyway.
        assert customer_login("۰۰۴۵۸۱۳۹۲۲").status == 200
        assert customer_login("٠٠٤٥٨١٣٩٢٢").status == 200

    def test_staff_credentials_do_not_work_on_the_customer_door(self) -> None:
        expect_error(customer_login("reza"), "validation")

    def test_a_deactivated_customer_cannot_sign_in(self) -> None:
        User.objects.filter(national_id=NATIONAL_IDS["amir"]).update(is_active=False)
        expect_error(customer_login(NATIONAL_IDS["amir"]), "invalid_credentials")


class TestFailedSignInAudit:
    def test_a_failed_customer_attempt_is_audited_without_the_full_id_or_the_password(self) -> None:
        customer_login(NATIONAL_IDS["amir"], "bad-password1")
        failed = list(AuditLog.objects.filter(action="auth_login_failed"))
        assert len(failed) == 1
        assert failed[0].actor is None
        assert failed[0].actor_role is None
        assert failed[0].target == "004•••••22"

        everything = json.dumps(
            list(AuditLog.objects.values("action", "target", "actor_name_en", "actor_name_fa")),
            ensure_ascii=False,
        )
        assert NATIONAL_IDS["amir"] not in everything
        assert "bad-password1" not in everything

        admin = staff_api("admin")
        seen = json.dumps(admin.audit(pageSize=100).data, ensure_ascii=False)
        assert NATIONAL_IDS["amir"] not in seen
        assert "bad-password1" not in seen
        assert "004•••••22" in seen

    def test_a_failed_staff_attempt_records_the_username_when_it_is_shaped_like_one(self) -> None:
        staff_login("Reza", "bad-password1")
        assert AuditLog.objects.get(action="auth_login_failed").target == "reza"

    @pytest.mark.parametrize(
        "typed", ["Tr0ub4dor&3 mistakenly typed here", "has space", "x", "a" * 21, "ünï", "1abc"]
    )
    def test_anything_else_typed_into_the_username_box_is_never_copied_into_the_log(
        self, typed: str
    ) -> None:
        staff_login(typed, "bad-password1")
        entry = AuditLog.objects.get(action="auth_login_failed")
        assert entry.target == "(invalid)"

    def test_a_wrong_password_for_a_deactivated_account_is_also_recorded(self) -> None:
        User.objects.filter(username="reza").update(is_active=False)
        staff_login("reza", DEMO_PASSWORD)
        assert AuditLog.objects.filter(action="auth_login_failed", target="reza").count() == 1

    def test_success_is_audited_with_the_actor(self) -> None:
        staff_login("reza")
        entry = AuditLog.objects.get(action="auth_login")
        assert entry.actor_id is not None
        assert str(entry.actor_id) == uid("u-reza")
        assert entry.actor_name_en == "Reza Karimi"
        assert entry.actor_role == "staff"

    def test_a_validation_failure_is_not_audited(self) -> None:
        customer_login("123")
        assert not AuditLog.objects.filter(action="auth_login_failed").exists()


class TestRegistration:
    def test_creates_a_customer_signs_them_in_and_stores_only_a_hash(self) -> None:
        payload = new_customer()
        reply = Api().post("/api/auth/register/", payload)
        assert reply.status == 201
        user = reply.data["user"]
        assert user["role"] == "customer"
        assert user["fullName"] == "Nima Ahmadi"
        assert user["nationalId"] == payload["nationalId"]
        assert user["phone"] == "09151112233"
        assert not CREDENTIAL_WORDS.search(json.dumps(user))

        stored = User.objects.get(pk=user["id"])
        assert "Strong1pass" not in stored.password
        assert check_password("Strong1pass", stored.password)

        token = reply.data["token"]
        assert Api(token).me().data["id"] == user["id"]
        assert customer_login(payload["nationalId"], "Strong1pass").status == 200

    def test_registration_is_audited(self) -> None:
        user = Api().post("/api/auth/register/", new_customer()).data["user"]
        entry = AuditLog.objects.get(action="auth_register")
        assert str(entry.actor_id) == user["id"]
        assert entry.target == ""

    def test_refuses_a_national_id_that_is_already_registered(self) -> None:
        reply = Api().post("/api/auth/register/", new_customer(nationalId=NATIONAL_IDS["amir"]))
        expect_error(reply, "national_id_taken")

    def test_refuses_a_mobile_number_that_is_already_registered(self) -> None:
        reply = Api().post("/api/auth/register/", new_customer(phone="09121234567"))
        expect_error(reply, "phone_taken")

    def test_a_duplicate_id_is_reported_before_a_duplicate_phone(self) -> None:
        reply = Api().post(
            "/api/auth/register/",
            new_customer(nationalId=NATIONAL_IDS["amir"], phone="09121234567"),
        )
        expect_error(reply, "national_id_taken")

    def test_a_failed_registration_leaves_no_half_created_account(self) -> None:
        before = User.objects.count()
        Api().post("/api/auth/register/", new_customer(phone="09121234567"))
        assert User.objects.count() == before
        assert not User.objects.filter(national_id=with_check_digit("123456789")).exists()

    @pytest.mark.parametrize(
        ("override", "field", "key"),
        [
            ({"nationalId": "1234567890"}, "nationalId", "validation.nationalId.checksum"),
            ({"nationalId": "123"}, "nationalId", "validation.nationalId.format"),
            ({"nationalId": "1111111111"}, "nationalId", "validation.nationalId.checksum"),
            ({"nationalId": ""}, "nationalId", "validation.nationalId.format"),
            ({"phone": "9151112233"}, "phone", "validation.phone"),
            ({"phone": "08151112233"}, "phone", "validation.phone"),
            ({"phone": "0915111223a"}, "phone", "validation.phone"),
            ({"postalCode": "123"}, "postalCode", "validation.postalCode"),
            ({"fullName": "A"}, "fullName", "validation.fullName"),
            ({"fullName": "   "}, "fullName", "validation.fullName"),
            ({"fullName": "x" * 101}, "fullName", "validation.fullName"),
            ({"address": "x"}, "address", "validation.address"),
            ({"address": "x" * 201}, "address", "validation.address"),
            ({"password": "short1"}, "password", "validation.password.min"),
            ({"password": "alllowercase"}, "password", "validation.password.mix"),
            ({"password": "12345678"}, "password", "validation.password.mix"),
            ({"password": "a1" * 65}, "password", "validation.password.max"),
        ],
    )
    def test_revalidates_on_the_server_with_the_frontends_message_keys(
        self, override: dict[str, Any], field: str, key: str
    ) -> None:
        reply = Api().post("/api/auth/register/", new_customer(**override))
        expect_error(reply, "validation")
        assert reply.data["errors"][field][0] == key
        assert list(reply.data["errors"]) == [field]

    def test_reports_every_problem_at_once_and_never_a_stock_english_sentence(self) -> None:
        reply = Api().post("/api/auth/register/", {})
        expect_error(reply, "validation")
        assert set(reply.data["errors"]) == {
            "fullName",
            "nationalId",
            "phone",
            "postalCode",
            "address",
            "password",
        }
        for messages in reply.data["errors"].values():
            assert messages == ["validation.required"] or messages[0].startswith("validation.")

    def test_digits_typed_in_persian_are_stored_as_ascii(self) -> None:
        national_id = with_check_digit("123456789")
        reply = Api().post(
            "/api/auth/register/",
            new_customer(nationalId="۱۲۳۴۵۶۷۸۹" + national_id[-1], phone="۰۹۱۵۱۱۱۲۲۳۳"),
        )
        assert reply.status == 201
        assert reply.data["user"]["nationalId"] == national_id
        assert reply.data["user"]["phone"] == "09151112233"

    def test_cannot_be_used_to_create_an_admin_or_a_staff_account(self) -> None:
        reply = Api().post(
            "/api/auth/register/",
            new_customer(
                role="admin",
                departmentIds=["loan", "vehicle"],
                isActive=False,
                username="root",
                id="00000000-0000-0000-0000-000000000001",
            ),
        )
        assert reply.status == 201
        user = reply.data["user"]
        assert user["role"] == "customer"
        assert user["isActive"] is True
        assert "departmentIds" not in user
        assert "username" not in user
        assert user["id"] != "00000000-0000-0000-0000-000000000001"
        stored = User.objects.get(pk=user["id"])
        assert (stored.role, stored.username, stored.department_ids) == ("customer", None, [])

    def test_the_password_is_not_trimmed_or_altered(self) -> None:
        reply = Api().post("/api/auth/register/", new_customer(password=" Strong1pass "))
        assert reply.status == 201
        stored = User.objects.get(pk=reply.data["user"]["id"])
        assert check_password(" Strong1pass ", stored.password)
        assert not check_password("Strong1pass", stored.password)


class TestSessions:
    def test_a_call_without_a_token_is_unauthenticated(self) -> None:
        reply = Api().me()
        expect_error(reply, "unauthenticated")
        assert reply.headers["WWW-Authenticate"].startswith("Bearer")

    def test_logout_ends_the_session(self) -> None:
        reply = Api().post(
            "/api/auth/login/staff/", {"username": "reza", "password": DEMO_PASSWORD}
        )
        client = Api(reply.data["token"])
        assert client.me().status == 200
        out = client.post("/api/auth/logout/")
        assert out.status == 204
        assert out.data is None
        expect_error(client.me(), "unauthenticated")

    def test_logout_is_idempotent_and_reveals_nothing(self) -> None:
        client = staff_api("reza")
        assert client.post("/api/auth/logout/").status == 204
        assert client.post("/api/auth/logout/").status == 204  # already revoked
        assert Api("f" * 64).post("/api/auth/logout/").status == 204  # unknown token
        assert Api("garbage").post("/api/auth/logout/").status == 204  # malformed
        assert Api().post("/api/auth/logout/").status == 204  # no token at all

    def test_logout_revokes_only_the_presented_token(self) -> None:
        first = staff_api("reza")
        second = staff_api("reza")
        first.post("/api/auth/logout/")
        assert first.me().status == 401
        assert second.me().status == 200

    def test_an_expired_token_is_treated_as_signed_out(self) -> None:
        client = staff_api("reza")
        assert client.token is not None
        age_token(client.token, expired=True)
        expect_error(client.me(), "unauthenticated")

    def test_a_revoked_token_is_treated_as_signed_out(self) -> None:
        client = staff_api("reza")
        assert client.token is not None
        age_token(client.token, revoked=True)
        expect_error(client.me(), "unauthenticated")

    def test_signing_in_as_someone_else_does_not_end_the_first_session(self) -> None:
        first = staff_api("reza")
        second = staff_api("sara")
        assert first.me().data["username"] == "reza"
        assert second.me().data["username"] == "sara"

    @pytest.mark.parametrize(
        "header",
        [
            "Bearer",
            "Bearer ",
            "Bearer short",
            "Bearer " + "g" * 64,
            "Bearer " + "A" * 64,  # tokens are lower-case hex; upper-case cannot be ours
            "Bearer " + "0" * 63,
            "Bearer " + "0" * 65,
            "Bearer " + "0" * 64 + " extra",
            "Bearer " + "0" * 64,  # well-formed but unknown
        ],
    )
    def test_a_malformed_or_unknown_bearer_token_is_unauthenticated(self, header: str) -> None:
        reply = Api().get("/api/auth/me/", HTTP_AUTHORIZATION=header)
        expect_error(reply, "unauthenticated")

    def test_another_authentication_scheme_is_the_same_as_no_credentials(self) -> None:
        reply = Api().get("/api/auth/me/", HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz")
        expect_error(reply, "unauthenticated")

    def test_the_scheme_name_is_case_insensitive(self) -> None:
        client = staff_api("reza")
        reply = Api().get("/api/auth/me/", HTTP_AUTHORIZATION=f"bearer {client.token}")
        assert reply.status == 200

    def test_a_deactivated_accounts_open_session_stops_working_at_once(self) -> None:
        sara = staff_api("sara")
        User.objects.filter(username="sara").update(is_active=False)
        expect_error(sara.me(), "unauthenticated")
        expect_error(staff_login("sara"), "invalid_credentials")

    def test_only_a_hash_of_the_token_is_stored(self) -> None:
        reply = staff_login("reza")
        token = reply.data["token"]
        stored = AccessToken.objects.get(user__username="reza")
        assert stored.key_hash == hashlib.sha256(token.encode()).hexdigest()
        assert token not in {stored.key_hash}
        assert not any(token in str(value) for value in AccessToken.objects.values_list())

    def test_a_token_lives_for_the_configured_time(self) -> None:
        staff_login("reza")
        stored = AccessToken.objects.get(user__username="reza")
        assert stored.expires_at - stored.created_at == settings.ACCESS_TOKEN_TTL
        assert timedelta(hours=8) == settings.ACCESS_TOKEN_TTL

    def test_signing_in_clears_that_accounts_dead_tokens(self) -> None:
        old = staff_api("reza")
        assert old.token is not None
        age_token(old.token, expired=True)
        dead_revoked = staff_api("reza")
        assert dead_revoked.token is not None
        age_token(dead_revoked.token, revoked=True)
        other = staff_api("sara")
        assert other.token is not None
        age_token(other.token, expired=True)

        staff_login("reza")
        assert AccessToken.objects.filter(user__username="reza").count() == 1
        assert AccessToken.objects.filter(user__username="sara").count() == 1  # not touched

    def test_me_returns_the_callers_own_profile(self) -> None:
        assert staff_api("ali").me().data["username"] == "ali"
        assert customer_api("hossein").me().data["nationalId"] == NATIONAL_IDS["hossein"]


class TestCredentialsNeverLeak:
    def test_no_response_contains_credential_fields(self) -> None:
        admin = staff_api("admin")
        listing = json.dumps(admin.get("/api/staff/").data)
        assert not CREDENTIAL_WORDS.search(listing)
        amir = customer_api("amir")
        assert not CREDENTIAL_WORDS.search(json.dumps(amir.me().data))
        assert not CREDENTIAL_WORDS.search(json.dumps(amir.mine().data))
        assert not CREDENTIAL_WORDS.search(json.dumps(admin.queue(pageSize=50).data))
        assert not CREDENTIAL_WORDS.search(json.dumps(admin.audit(pageSize=100).data))

    def test_last_login_is_recorded_but_not_exposed(self) -> None:
        reply = staff_login("reza")
        assert "lastLogin" not in reply.data["user"]
        assert User.objects.get(username="reza").last_login is not None


class TestThrottling:
    @pytest.fixture
    def tight(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            ScopedRateThrottle, "THROTTLE_RATES", {"auth_login": "3/min", "auth_register": "2/min"}
        )

    def test_sign_in_attempts_are_limited_per_client(self, tight: None) -> None:
        for _ in range(3):
            assert staff_login("reza", "wrong-pass1").status == 401
        blocked = staff_login("reza", DEMO_PASSWORD)  # even the right password is refused now
        expect_error(blocked, "network")
        assert blocked.status == 429
        assert int(blocked.headers["Retry-After"]) >= 1

    def test_customer_and_staff_sign_in_share_one_budget(self, tight: None) -> None:
        for _ in range(2):
            staff_login("reza", "wrong-pass1")
        customer_login(NATIONAL_IDS["amir"], "wrong-pass1")
        assert customer_login(NATIONAL_IDS["amir"], DEMO_PASSWORD).status == 429

    def test_registration_has_its_own_budget(self, tight: None) -> None:
        for number in range(2):
            reply = Api().post(
                "/api/auth/register/",
                new_customer(
                    nationalId=with_check_digit(f"22345678{number}"), phone=f"0915111223{number}"
                ),
            )
            assert reply.status == 201
        blocked = Api().post("/api/auth/register/", new_customer())
        assert blocked.status == 429
        assert staff_login("reza").status == 200  # the sign-in budget is untouched

    def test_other_endpoints_are_not_throttled(self, tight: None) -> None:
        client = staff_api("reza")
        for _ in range(10):
            assert client.me().status == 200

    def test_a_spoofed_forwarding_header_does_not_buy_extra_attempts(self, tight: None) -> None:
        for number in range(3):
            Api().post(
                "/api/auth/login/staff/",
                {"username": "reza", "password": "wrong-pass1"},
                HTTP_X_FORWARDED_FOR=f"10.0.0.{number}",
            )
        blocked = Api().post(
            "/api/auth/login/staff/",
            {"username": "reza", "password": DEMO_PASSWORD},
            HTTP_X_FORWARDED_FOR="10.9.9.9",
        )
        assert blocked.status == 429

    def test_validation_failures_count_against_the_budget_too(self, tight: None) -> None:
        for _ in range(3):
            customer_login("123")
        assert customer_login("123").status == 429
