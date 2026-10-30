"""Persian-locale helpers (port of the frontend's ``persianUtils.test.ts``)."""

from __future__ import annotations

import random
import re

import pytest

from apps.core.persian import (
    complete_national_id,
    generate_tracking_code,
    is_valid_national_id,
    mask_national_id,
    normalize_digits,
    to_persian_digits,
)
from tests.helpers import NATIONAL_IDS, random_valid_national_id, with_check_digit

REPDIGIT = re.compile(r"([0-9])\1{9}")


class TestIsValidNationalId:
    def test_accepts_the_seeded_demo_ids(self) -> None:
        for national_id in NATIONAL_IDS.values():
            assert is_valid_national_id(national_id), national_id

    def test_accepts_codes_generated_with_a_correct_check_digit(self) -> None:
        rng = random.Random(1)
        checked = 0
        for _ in range(3000):
            national_id = random_valid_national_id(rng)
            if REPDIGIT.fullmatch(national_id):
                continue  # repdigits are rejected on purpose
            assert is_valid_national_id(national_id), national_id
            checked += 1
        assert checked > 2900

    def test_rejects_any_code_whose_last_digit_is_wrong(self) -> None:
        rng = random.Random(2)
        for _ in range(500):
            valid = random_valid_national_id(rng)
            wrong = (int(valid[9]) + 1 + rng.randrange(9)) % 10  # any digit but the right one
            assert not is_valid_national_id(f"{valid[:9]}{wrong}"), valid

    @pytest.mark.parametrize(
        "bad",
        [
            "1111111111",
            "0000000000",
            "004581392",
            "00458139222",
            "00458139a2",
            "",
            "۰۰۴۵۸۱۳۹۲۲",  # Persian digits must be normalised *before* validation
            "0045813922\n",  # ``$`` would accept a trailing newline; fullmatch does not
            " 0045813922",
            "٠٠٤٥٨١٣٩٢٢",
        ],
    )
    def test_rejects_malformed_codes(self, bad: str) -> None:
        assert not is_valid_national_id(bad)

    def test_checksum_matches_an_independent_implementation(self) -> None:
        # Hand-computed: digits 0045813922 → 0*10+0*9+4*8+5*7+8*6+1*5+3*4+9*3+2*2 = 163;
        # 163 % 11 = 9; remainder >= 2 so the check digit is 11 - 9 = 2.
        assert with_check_digit("004581392") == "0045813922"


class TestCompleteNationalId:
    def test_appends_a_valid_check_digit(self) -> None:
        rng = random.Random(3)
        for _ in range(300):
            nine = f"{rng.randrange(10**9):09d}"
            assert is_valid_national_id(complete_national_id(nine)), nine

    def test_never_produces_a_repdigit(self) -> None:
        assert not REPDIGIT.fullmatch(complete_national_id("000000000"))
        assert is_valid_national_id(complete_national_id("000000000"))

    @pytest.mark.parametrize("bad", ["", "12345678", "1234567890", "12345678a", "۱۲۳۴۵۶۷۸۹"])
    def test_requires_exactly_nine_ascii_digits(self, bad: str) -> None:
        with pytest.raises(ValueError, match="nine digits"):
            complete_national_id(bad)


class TestDigitConversion:
    def test_round_trips_ascii_and_persian_digits(self) -> None:
        assert to_persian_digits("0045813922") == "۰۰۴۵۸۱۳۹۲۲"
        assert normalize_digits("۰۰۴۵۸۱۳۹۲۲") == "0045813922"
        assert to_persian_digits(1405) == "۱۴۰۵"

    def test_normalises_arabic_indic_digits_and_leaves_everything_else_alone(self) -> None:
        assert normalize_digits("٠٩١٢٣٤٥٦٧٨٩") == "09123456789"
        assert normalize_digits("abc ۱۲ 34") == "abc 12 34"
        assert normalize_digits("") == ""

    def test_normalising_is_idempotent(self) -> None:
        once = normalize_digits("۰۹۱۲ ٣٤٥ 678")
        assert normalize_digits(once) == once == "0912 345 678"


class TestGenerateTrackingCode:
    def test_is_always_exactly_ten_ascii_digits(self) -> None:
        for _ in range(500):
            assert re.fullmatch(r"[0-9]{10}", generate_tracking_code())

    def test_is_not_constant(self) -> None:
        assert len({generate_tracking_code() for _ in range(50)}) > 40


class TestMaskNationalId:
    def test_keeps_the_first_three_and_last_two_digits(self) -> None:
        assert mask_national_id("0045813922") == "004•••••22"
        assert len(mask_national_id("0045813922")) == 10

    def test_never_echoes_a_short_value_back(self) -> None:
        assert mask_national_id("123") == "•••"
        assert mask_national_id("12345") == "•••••"
        assert mask_national_id("") == ""

    def test_hides_the_middle_of_longer_input_too(self) -> None:
        assert mask_national_id("123456") == "123•56"
