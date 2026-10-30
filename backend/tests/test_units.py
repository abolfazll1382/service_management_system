"""Small pure helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest

from apps.core.ids import parse_uuid
from apps.core.messages import error_text, preferred_language
from apps.core.pagination import Page, paginate
from apps.core.serializers import iso_utc
from apps.core.text import contains_unstorable_characters
from apps.core.validators import (
    national_id_validator,
    new_password_validator,
    phone_validator,
    postal_code_validator,
    username_validator,
)


class TestParseUuid:
    def test_accepts_only_the_canonical_form(self) -> None:
        value = uuid.uuid4()
        assert parse_uuid(str(value)) == value
        assert parse_uuid(value) == value

    @pytest.mark.parametrize(
        "bad",
        [
            None,
            5,
            "",
            "abc",
            "req-seed-1",
            "{" + str(uuid.uuid4()) + "}",
            "urn:uuid:" + str(uuid.uuid4()),
            uuid.uuid4().hex,  # 32 hex digits: valid for uuid.UUID() but not canonical
            str(uuid.uuid4()) + " ",
            str(uuid.uuid4()).upper()[:-1] + "G",
        ],
    )
    def test_everything_else_is_simply_not_an_id(self, bad: object) -> None:
        assert parse_uuid(bad) is None

    def test_upper_case_is_accepted(self) -> None:
        value = uuid.uuid4()
        assert parse_uuid(str(value).upper()) == value


class TestMessages:
    def test_error_text_falls_back_to_english_for_an_unknown_language(self) -> None:
        assert error_text("forbidden", "fa") != error_text("forbidden", "en")
        assert error_text("forbidden") == error_text("forbidden", "en")

    @pytest.mark.parametrize(
        ("header", "expected"),
        [
            ("fa", "fa"),
            ("en-GB", "en"),
            ("fa-IR;q=0.3, en;q=0.8", "en"),
            ("zz", "en"),
            (None, "en"),
        ],
    )
    def test_preferred_language(self, header: str | None, expected: str) -> None:
        assert preferred_language(header) == expected


class TestText:
    @pytest.mark.parametrize("text", ["a\x00b", "\ud800", "x\udfffy", "\x00"])
    def test_detects_what_postgresql_cannot_store(self, text: str) -> None:
        assert contains_unstorable_characters(text)

    @pytest.mark.parametrize("text", ["", "plain", "فارسی", "😀", "tab\tnewline\n", "\x01 control"])
    def test_everything_else_is_storable(self, text: str) -> None:
        assert not contains_unstorable_characters(text)


class TestTimestamps:
    def test_wire_format_is_utc_with_milliseconds_and_a_z_suffix(self) -> None:
        assert (
            iso_utc(datetime(2026, 10, 5, 8, 30, 0, 123456, tzinfo=UTC))
            == "2026-10-05T08:30:00.123Z"
        )
        assert iso_utc(datetime(2026, 10, 5, 8, 30, tzinfo=UTC)) == "2026-10-05T08:30:00.000Z"

    def test_other_zones_are_converted(self) -> None:
        tehran = timezone(timedelta(hours=3, minutes=30))
        assert iso_utc(datetime(2026, 10, 5, 12, 0, tzinfo=tehran)) == "2026-10-05T08:30:00.000Z"


class TestValidators:
    def test_phone(self) -> None:
        phone_validator("09121234567")
        for bad in ("9121234567", "0912123456", "091212345678", "08121234567", "09121234567\n"):
            with pytest.raises(Exception):  # noqa: B017
                phone_validator(bad)

    def test_the_end_of_string_is_not_a_newline(self) -> None:
        for validator, value in (
            (postal_code_validator, "1234567890\n"),
            (username_validator, "reza\n"),
            (national_id_validator(check_digit=False), "0045813922\n"),
        ):
            with pytest.raises(Exception):  # noqa: B017
                validator(value)

    def test_national_id_reports_shape_before_checksum(self) -> None:
        from rest_framework import serializers

        check = national_id_validator(check_digit=True)
        with pytest.raises(serializers.ValidationError) as short:
            check("123")
        assert list(short.value.detail) == ["validation.nationalId.format"]
        with pytest.raises(serializers.ValidationError) as wrong:
            check("1234567890")
        assert list(wrong.value.detail) == ["validation.nationalId.checksum"]
        check("0045813922")
        national_id_validator(check_digit=False)("1234567890")

    def test_unicode_digits_are_not_digits(self) -> None:
        for validator in (phone_validator, postal_code_validator):
            with pytest.raises(Exception):  # noqa: B017
                validator("۰۹۱۲۱۲۳۴۵۶۷" if validator is phone_validator else "۱۲۳۴۵۶۷۸۹۰")

    def test_password_needs_an_ascii_letter_and_digit(self) -> None:
        new_password_validator("abc12345")
        for bad in ("abcdefgh", "12345678", "پسورد۱۲۳۴۵"):
            with pytest.raises(Exception):  # noqa: B017
                new_password_validator(bad)


class TestPagination:
    def test_the_envelope(self) -> None:
        page = Page(items=[1, 2], total=5, page=2, page_size=2)
        assert page.envelope(["a", "b"], counts={"x": 1}) == {
            "items": ["a", "b"],
            "total": 5,
            "page": 2,
            "pageSize": 2,
            "counts": {"x": 1},
        }

    @pytest.mark.django_db
    @pytest.mark.usefixtures("demo")
    def test_slicing_and_out_of_range_pages(self) -> None:
        from apps.users.models import User

        queryset = User.objects.order_by("username", "pk")
        assert [len(paginate(queryset, page=n, page_size=3).items) for n in (1, 2, 3, 4)] == [
            3,
            3,
            2,
            0,
        ]
        assert paginate(queryset, page=2, page_size=3).total == 8
        assert paginate(queryset, page=99, page_size=3).items == []
