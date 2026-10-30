"""Persian-locale helpers: National ID checksum, digit conversion, tracking codes.

Mirrors ``src/lib/utils/persianUtils.ts`` and ``mask.ts`` in the frontend. These are *structural*
checks only: :func:`is_valid_national_id` confirms a number is well-formed (the public modulo-11
checksum); it cannot confirm the number is assigned to anyone, and nothing here claims otherwise.
"""

from __future__ import annotations

import re
import secrets

_PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_ARABIC_INDIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ASCII_DIGITS = "0123456789"

_TO_ASCII = str.maketrans(_PERSIAN_DIGITS + _ARABIC_INDIC_DIGITS, _ASCII_DIGITS * 2)
_TO_PERSIAN = str.maketrans(_ASCII_DIGITS, _PERSIAN_DIGITS)

# `[0-9]`, never `\d`: in Python `\d` also matches every other Unicode decimal digit.
_TEN_DIGITS = re.compile(r"[0-9]{10}")
_REPDIGIT = re.compile(r"([0-9])\1{9}")


def normalize_digits(value: str) -> str:
    """Persian (۰-۹) and Arabic-Indic (٠-٩) digits → ASCII; everything else is left alone."""
    return value.translate(_TO_ASCII)


def to_persian_digits(value: str | int) -> str:
    """ASCII → Persian digits. Display-only helper (stored values stay ASCII)."""
    return str(value).translate(_TO_PERSIAN)


def is_valid_national_id(value: str) -> bool:
    """Validate an Iranian National ID (کد ملی).

    The first nine digits are weighted 10…2, summed and reduced mod 11; that remainder decides the
    tenth digit. Repeated-digit codes ("1111111111") pass the arithmetic for some digits but are
    never issued, so they are rejected explicitly.
    """
    if not _TEN_DIGITS.fullmatch(value) or _REPDIGIT.fullmatch(value):
        return False
    digits = [int(ch) for ch in value]
    remainder = sum(digit * (10 - index) for index, digit in enumerate(digits[:9])) % 11
    expected = remainder if remainder < 2 else 11 - remainder
    return digits[9] == expected


def complete_national_id(first_nine: str) -> str:
    """Append the check digit to nine digits. For sample/test data only: it manufactures a
    *well-formed* number, which says nothing about whether anyone holds it."""
    if not re.fullmatch(r"[0-9]{9}", first_nine):
        raise ValueError("Expected exactly nine digits")
    remainder = sum(int(ch) * (10 - i) for i, ch in enumerate(first_nine)) % 11
    completed = f"{first_nine}{remainder if remainder < 2 else 11 - remainder}"
    if _REPDIGIT.fullmatch(completed):  # e.g. 0000000000: nudge the first digit
        return complete_national_id(f"{(int(first_nine[0]) + 1) % 10}{first_nine[1:]}")
    return completed


def mask_national_id(value: str) -> str:
    """Keep the first three and last two digits (``0045813922`` → ``004•••••22``).

    Enough for an administrator to tell two attempts apart, without putting a full national ID
    into the audit log.
    """
    if len(value) < 6:
        return "•" * len(value)
    return f"{value[:3]}{'•' * (len(value) - 5)}{value[-2:]}"


def generate_tracking_code() -> str:
    """Ten random decimal digits from the OS CSPRNG. Uniqueness is enforced by the database."""
    return f"{secrets.randbelow(10**10):010d}"
