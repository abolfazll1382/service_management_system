"""Password hashing with the production hasher (the rest of the suite uses a fast one)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.test import override_settings

from apps.users import services as user_services
from apps.users.models import User
from tests.helpers import DEMO_PASSWORD, Api, expect_error, staff_api, uid, with_check_digit

PRODUCTION_HASHERS = [
    "apps.core.hashers.PortalArgon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

pytestmark = pytest.mark.django_db


@pytest.fixture
def production_hashers() -> Iterator[None]:
    with override_settings(PASSWORD_HASHERS=PRODUCTION_HASHERS):
        user_services._decoy_hash.cache_clear()
        yield
    user_services._decoy_hash.cache_clear()


@pytest.mark.usefixtures("production_hashers")
class TestArgon2:
    def test_new_hashes_are_argon2id_with_the_configured_cost(self) -> None:
        encoded = make_password("Strong1pass")
        assert encoded.startswith("argon2$argon2id$v=19$")
        assert f"m={settings.ARGON2_MEMORY_COST_KIB},t={settings.ARGON2_TIME_COST},p=" in encoded
        assert (settings.ARGON2_TIME_COST, settings.ARGON2_MEMORY_COST_KIB) == (2, 19_456)
        assert settings.ARGON2_PARALLELISM == 1

    def test_the_cost_is_small_enough_for_a_small_container(self) -> None:
        # Django's stock Argon2 hasher would use 100 MiB per hash.
        assert settings.ARGON2_MEMORY_COST_KIB <= 64 * 1024

    def test_hashes_are_salted_and_verify_only_the_right_password(self) -> None:
        first, second = make_password("Strong1pass"), make_password("Strong1pass")
        assert first != second
        assert check_password("Strong1pass", first)
        assert not check_password("Strong1pasS", first)
        assert not check_password("", first)

    def test_long_unicode_and_odd_passwords_work(self) -> None:
        for password in ("Pässwörd1😀", "گذرواژه۱a", "a1" + "x" * 126, "  spaces 1  "):
            assert check_password(password, make_password(password))

    def test_the_decoy_used_for_unknown_users_is_a_real_hash_in_the_current_format(self) -> None:
        assert identify_hasher(user_services._decoy_hash()).algorithm == "argon2"

    def test_an_unknown_user_costs_the_same_work_as_a_wrong_password(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[str, str]] = []
        real = check_password

        def spy(password: str, encoded: str, *args: Any, **kwargs: Any) -> bool:
            calls.append((password, encoded))
            return real(password, encoded, *args, **kwargs)

        monkeypatch.setattr(user_services, "check_password", spy)
        reply = Api().post("/api/auth/login/staff/", {"username": "nobody", "password": "x1y2z3w4"})
        expect_error(reply, "invalid_credentials")
        assert calls == [("x1y2z3w4", user_services._decoy_hash())]

    def test_registering_and_signing_in_work_end_to_end(self) -> None:
        national_id = with_check_digit("123456789")
        body = {
            "fullName": "Nima Ahmadi",
            "nationalId": national_id,
            "phone": "09151112233",
            "postalCode": "1234567890",
            "address": "Mashhad, Sajjad Blvd, No. 4",
            "password": "Pässwörd1😀",
        }
        assert Api().post("/api/auth/register/", body).status == 201
        stored = User.objects.get(national_id=national_id)
        assert stored.password.startswith("argon2$argon2id$")
        login = Api().post(
            "/api/auth/login/customer/", {"nationalId": national_id, "password": "Pässwörd1😀"}
        )
        assert login.status == 200
        assert (
            Api()
            .post(
                "/api/auth/login/customer/", {"nationalId": national_id, "password": "Passwörd1😀"}
            )
            .status
            == 401
        )

    def test_an_older_pbkdf2_hash_still_works_and_is_upgraded_on_the_next_sign_in(self) -> None:
        legacy = make_password(DEMO_PASSWORD, hasher="pbkdf2_sha256")
        assert legacy.startswith("pbkdf2_sha256$")
        User.objects.create(
            id=uid("u-reza"),
            role="staff",
            username="reza",
            name_fa="رضا",
            name_en="Reza",
            department_ids=["loan"],
            password=legacy,
        )
        reply = Api().post(
            "/api/auth/login/staff/", {"username": "reza", "password": DEMO_PASSWORD}
        )
        assert reply.status == 200
        upgraded = User.objects.get(username="reza").password
        assert upgraded.startswith("argon2$argon2id$")
        assert check_password(DEMO_PASSWORD, upgraded)

    def test_a_password_with_characters_that_cannot_be_encoded_is_a_validation_error(self) -> None:
        # A lone surrogate would crash the hasher's UTF-8 encoding: it must never reach it.
        raw = b'{"username":"reza","password":"x\\ud800y"}'
        expect_error(Api().call("post", "/api/auth/login/staff/", raw=raw), "validation")
        national_id = with_check_digit("123456789")
        body = (
            b'{"fullName":"Nima Ahmadi","nationalId":"' + national_id.encode() + b'",'
            b'"phone":"09151112233","postalCode":"1234567890",'
            b'"address":"Mashhad, Sajjad Blvd","password":"Pass\\ud800word1"}'
        )
        expect_error(Api().call("post", "/api/auth/register/", raw=body), "validation")

    def test_the_demo_seed_is_hashed_with_argon2_too(self) -> None:
        from apps.core.demo.service import DemoService

        DemoService.seed()
        assert User.objects.get(username="reza").password.startswith("argon2$argon2id$")
        assert staff_api("reza").me().status == 200


class TestPasswordRules:
    @pytest.mark.usefixtures("demo")
    def test_the_documented_demo_password_satisfies_the_password_rule(self) -> None:
        from apps.users.serializers import RegisterInputSerializer

        field = RegisterInputSerializer().fields["password"]
        assert field.run_validation(DEMO_PASSWORD) == DEMO_PASSWORD

    @pytest.mark.parametrize(
        ("password", "ok"),
        [
            ("Strong1pass", True),
            ("abcdefg1", True),
            ("1234567a", True),
            ("short1a", False),
            ("onlyletters", False),
            ("12345678", False),
            ("پسوردفارسی۱۲۳", False),  # needs an ASCII letter and an ASCII digit
            ("a1" * 64, True),
            ("a1" * 65, False),
        ],
    )
    def test_the_rule_is_eight_to_128_characters_with_a_letter_and_a_digit(
        self, password: str, ok: bool
    ) -> None:
        from rest_framework import serializers

        from apps.users.serializers import NewPasswordField

        field = NewPasswordField()
        if ok:
            assert field.run_validation(password) == password
        else:
            with pytest.raises(serializers.ValidationError):
                field.run_validation(password)
