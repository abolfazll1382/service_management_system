"""User-facing texts for the error contract, in the frontend's two languages.

* ``ERRORS`` – the human sentence for each API error *code* (the ``detail`` field of an error
  response). Taken verbatim from the frontend's ``errors.*`` dictionaries.
* ``VALIDATION_KEYS`` – the language-neutral keys placed in ``errors.<field>`` lists. They are the
  frontend's ``validation.*`` dictionary keys, so the client translates them with its own ``t()``;
  the backend never embeds a sentence there. The two keys marked *backend-only* have no frontend
  counterpart yet (see README).
"""

from __future__ import annotations

from typing import Final, Literal

Language = Literal["en", "fa"]
SUPPORTED_LANGUAGES: Final[tuple[Language, ...]] = ("en", "fa")
DEFAULT_LANGUAGE: Final[Language] = "en"

ERRORS: Final[dict[Language, dict[str, str]]] = {
    "en": {
        "unauthenticated": "Your session has ended. Please sign in again.",
        "forbidden": "You don't have permission to do that.",
        "not_found": "We couldn't find what you asked for.",
        "validation": "Some of the information isn't valid. Please check and try again.",
        "invalid_credentials": "Incorrect ID/username or password.",
        "national_id_taken": "An account with this National ID already exists.",
        "phone_taken": "An account with this mobile number already exists.",
        "username_taken": "This username is already taken.",
        "service_unavailable": "This service isn't accepting requests right now.",
        "invalid_transition": "That status change isn't allowed from the current status.",
        "request_closed": "This request is closed and can't be changed.",
        "network": "A network error occurred. Please try again.",
    },
    "fa": {
        "unauthenticated": "نشست شما به پایان رسیده است. لطفاً دوباره وارد شوید.",
        "forbidden": "شما اجازه انجام این کار را ندارید.",
        "not_found": "مورد درخواستی پیدا نشد.",
        "validation": "برخی اطلاعات معتبر نیستند. لطفاً بررسی و دوباره تلاش کنید.",
        "invalid_credentials": "کد ملی/نام کاربری یا گذرواژه نادرست است.",
        "national_id_taken": "حسابی با این کد ملی قبلاً ثبت شده است.",
        "phone_taken": "حسابی با این شماره موبایل قبلاً ثبت شده است.",
        "username_taken": "این نام کاربری قبلاً گرفته شده است.",
        "service_unavailable": "این خدمت در حال حاضر درخواست نمی‌پذیرد.",
        "invalid_transition": "تغییر وضعیت از حالت فعلی مجاز نیست.",
        "request_closed": "این درخواست بسته شده و قابل تغییر نیست.",
        "network": "خطای شبکه رخ داد. لطفاً دوباره تلاش کنید.",
    },
}

# Field-level validation keys (values of ``errors.<field>`` lists).
V_REQUIRED: Final = "validation.required"
V_INVALID: Final = "validation.invalid"  # backend-only: generic fallback
V_FULL_NAME: Final = "validation.fullName"
V_NATIONAL_ID_FORMAT: Final = "validation.nationalId.format"
V_NATIONAL_ID_CHECKSUM: Final = "validation.nationalId.checksum"
V_PHONE: Final = "validation.phone"
V_POSTAL_CODE: Final = "validation.postalCode"
V_ADDRESS: Final = "validation.address"
V_PASSWORD_MIN: Final = "validation.password.min"
V_PASSWORD_MIX: Final = "validation.password.mix"
V_PASSWORD_MAX: Final = "validation.password.max"  # backend-only: upper bound on hashing input
V_USERNAME: Final = "validation.username"
V_DESCRIPTION_MIN: Final = "validation.description.min"
V_DESCRIPTION_MAX: Final = "validation.description.max"
V_NUMBER_INVALID: Final = "validation.number.invalid"
V_NUMBER_MIN: Final = "validation.number.min"
V_NUMBER_MAX: Final = "validation.number.max"
V_TEXT_MAX: Final = "validation.text.max"
V_SELECT: Final = "validation.select"
V_NAMES: Final = "validation.names"
V_DEPARTMENTS: Final = "validation.departments"
V_NOTE_REQUIRED: Final = "validation.note.required"

VALIDATION_KEYS: Final[frozenset[str]] = frozenset(
    {
        V_REQUIRED,
        V_INVALID,
        V_FULL_NAME,
        V_NATIONAL_ID_FORMAT,
        V_NATIONAL_ID_CHECKSUM,
        V_PHONE,
        V_POSTAL_CODE,
        V_ADDRESS,
        V_PASSWORD_MIN,
        V_PASSWORD_MIX,
        V_PASSWORD_MAX,
        V_USERNAME,
        V_DESCRIPTION_MIN,
        V_DESCRIPTION_MAX,
        V_NUMBER_INVALID,
        V_NUMBER_MIN,
        V_NUMBER_MAX,
        V_TEXT_MAX,
        V_SELECT,
        V_NAMES,
        V_DEPARTMENTS,
        V_NOTE_REQUIRED,
    }
)

BACKEND_ONLY_KEYS: Final[frozenset[str]] = frozenset({V_INVALID, V_PASSWORD_MAX})


def error_text(code: str, language: Language = DEFAULT_LANGUAGE) -> str:
    """The sentence for an error code in ``language`` (English if the code is unknown)."""
    return ERRORS[language].get(code) or ERRORS[DEFAULT_LANGUAGE][code]


def preferred_language(header: str | None) -> Language:
    """Pick ``fa`` or ``en`` from an ``Accept-Language`` header (highest q wins, ties by order).

    Anything unparsable or unsupported falls back to English; a header is never a reason to fail.
    """
    if not header:
        return DEFAULT_LANGUAGE
    best: tuple[float, int, Language] | None = None
    for position, part in enumerate(header.split(",")):
        tag, _, params = part.partition(";")
        primary = tag.strip().lower().split("-")[0]
        language = next((lang for lang in SUPPORTED_LANGUAGES if lang == primary), None)
        if language is None:
            continue
        weight = 1.0
        for param in params.split(";"):
            name, _, value = param.partition("=")
            if name.strip().lower() == "q":
                try:
                    weight = float(value)
                except ValueError:
                    weight = 0.0
        if weight <= 0:
            continue
        candidate = (-weight, position, language)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else DEFAULT_LANGUAGE
