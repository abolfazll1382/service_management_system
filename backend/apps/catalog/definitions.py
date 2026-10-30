"""The built-in service catalogue, as plain data.

This is a 1:1 port of ``src/lib/catalog/services.ts``. Each entry lists the extra fields the service
needs; the frontend's apply wizard and this backend's ``details`` validation are both derived from
that list. ``CatalogService.sync_definitions`` loads it into the database (idempotently), after which
the *database* is the source of truth — so an operator can add or change services without a deploy,
and the code here is only the initial content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.core.choices import Department
from apps.core.persian import to_persian_digits

Localized = dict[str, str]
FieldDefinition = dict[str, Any]


def _l(fa: str, en: str) -> Localized:
    return {"fa": fa, "en": en}


def _text(key: str, fa: str, en: str, *, required: bool, max_length: int) -> FieldDefinition:
    return {
        "kind": "text",
        "key": key,
        "label": _l(fa, en),
        "required": required,
        "maxLength": max_length,
    }


def _number(
    key: str,
    fa: str,
    en: str,
    *,
    minimum: int,
    maximum: int,
    unit: Localized | None = None,
    required: bool = True,
) -> FieldDefinition:
    definition: FieldDefinition = {
        "kind": "number",
        "key": key,
        "label": _l(fa, en),
        "required": required,
        "min": minimum,
        "max": maximum,
    }
    if unit is not None:
        definition["unit"] = unit
    return definition


def _select(
    key: str,
    fa: str,
    en: str,
    options: list[dict[str, Any]],
    *,
    required: bool = True,
) -> FieldDefinition:
    return {
        "kind": "select",
        "key": key,
        "label": _l(fa, en),
        "required": required,
        "options": options,
    }


def _option(value: str, fa: str, en: str) -> dict[str, Any]:
    return {"value": value, "label": _l(fa, en)}


def _months(count: int) -> dict[str, Any]:
    return _option(str(count), f"{to_persian_digits(count)} ماه", f"{count} months")


@dataclass(frozen=True, slots=True)
class ServiceDefinition:
    id: str
    department: str
    title: Localized
    summary: Localized
    description: Localized
    requirements: tuple[Localized, ...]
    eta_days: int
    fields: tuple[FieldDefinition, ...]


_IRR = _l("ریال", "IRR")

SERVICE_DEFINITIONS: tuple[ServiceDefinition, ...] = (
    ServiceDefinition(
        id="personal-loan",
        department=Department.LOAN,
        title=_l("وام شخصی", "Personal loan"),
        summary=_l(
            "تأمین مالی نیازهای شخصی با اقساط ماهانه",
            "Finance personal needs with monthly installments",
        ),
        description=_l(
            "پس از ثبت درخواست، کارشناس تسهیلات مبلغ و مدت بازپرداخت موردنظر شما را بررسی می‌کند و نتیجه را از همین‌جا اعلام می‌کند.",
            "After you submit, a loan officer reviews the amount and repayment term you ask for and posts the outcome here.",
        ),
        requirements=(
            _l(
                "مبلغ و مدت بازپرداخت موردنظر را تعیین کنید", "Decide the amount and repayment term"
            ),
            _l(
                "هدف از دریافت وام را به‌طور خلاصه بنویسید",
                "Prepare a short note on what the loan is for",
            ),
        ),
        eta_days=5,
        fields=(
            _number(
                "amount",
                "مبلغ درخواستی",
                "Requested amount",
                minimum=10_000_000,
                maximum=1_000_000_000,
                unit=_IRR,
            ),
            _select(
                "termMonths",
                "مدت بازپرداخت",
                "Repayment term",
                [_months(12), _months(24), _months(36), _months(48)],
            ),
            _text("purpose", "هدف از دریافت وام", "Purpose", required=True, max_length=120),
        ),
    ),
    ServiceDefinition(
        id="business-loan",
        department=Department.LOAN,
        title=_l("تسهیلات کسب‌وکار", "Business loan"),
        summary=_l("سرمایه در گردش و توسعه کسب‌وکار", "Working capital and growth financing"),
        description=_l(
            "کارشناس تسهیلات نیاز مالی کسب‌وکار شما را بررسی می‌کند و در صورت نیاز مدارک تکمیلی می‌خواهد.",
            "A loan officer reviews your business financing need and asks for supporting documents if required.",
        ),
        requirements=(
            _l("حوزه فعالیت کسب‌وکار را مشخص کنید", "Know your business field"),
            _l("برآورد مبلغ موردنیاز را آماده کنید", "Prepare an estimate of the amount you need"),
        ),
        eta_days=10,
        fields=(
            _number(
                "amount",
                "مبلغ درخواستی",
                "Requested amount",
                minimum=50_000_000,
                maximum=5_000_000_000,
                unit=_IRR,
            ),
            _select(
                "termMonths",
                "مدت بازپرداخت",
                "Repayment term",
                [_months(12), _months(24), _months(36), _months(60)],
            ),
            _text("businessField", "حوزه فعالیت", "Business field", required=True, max_length=80),
        ),
    ),
    ServiceDefinition(
        id="steel-supply",
        department=Department.RAW_MATERIAL,
        title=_l("تأمین فولاد", "Steel supply"),
        summary=_l(
            "ورق، میلگرد و پروفیل برای پروژه‌های تولیدی",
            "Sheet, rebar and profiles for production",
        ),
        description=_l(
            "درخواست تأمین فولاد به کارشناس مواد اولیه ارجاع می‌شود تا موجودی و زمان تحویل را اعلام کند.",
            "Your steel request goes to the raw-materials team, who confirm stock and delivery time.",
        ),
        requirements=(
            _l("نوع فولاد و مقدار موردنیاز را مشخص کنید", "Know the steel type and quantity"),
            _l("شهر تحویل را اعلام کنید", "Decide the delivery city"),
        ),
        eta_days=7,
        fields=(
            _select(
                "material",
                "نوع فولاد",
                "Steel type",
                [
                    _option("sheet", "ورق", "Sheet"),
                    _option("rebar", "میلگرد", "Rebar"),
                    _option("profile", "پروفیل", "Profile"),
                ],
            ),
            _number(
                "quantity",
                "مقدار",
                "Quantity",
                minimum=1,
                maximum=500,
                unit=_l("تن", "tons"),
            ),
            _text("deliveryCity", "شهر تحویل", "Delivery city", required=True, max_length=60),
        ),
    ),
    ServiceDefinition(
        id="packaging-supply",
        department=Department.RAW_MATERIAL,
        title=_l("تأمین مواد بسته‌بندی", "Packaging supply"),
        summary=_l(
            "کارتن، پلاستیک و شیشه برای بسته‌بندی محصول",
            "Cardboard, plastic and glass for product packaging",
        ),
        description=_l(
            "کارشناس مواد اولیه درخواست شما را بررسی و زمان تأمین را اعلام می‌کند.",
            "The raw-materials team reviews your request and confirms the supply time.",
        ),
        requirements=(
            _l(
                "نوع ماده و تعداد موردنیاز را مشخص کنید",
                "Know the material type and quantity",
            ),
            _l("شهر تحویل را اعلام کنید", "Decide the delivery city"),
        ),
        eta_days=5,
        fields=(
            _select(
                "material",
                "نوع ماده",
                "Material",
                [
                    _option("cardboard", "کارتن", "Cardboard"),
                    _option("plastic", "پلاستیک", "Plastic"),
                    _option("glass", "شیشه", "Glass"),
                ],
            ),
            _number(
                "quantity",
                "تعداد",
                "Quantity",
                minimum=100,
                maximum=1_000_000,
                unit=_l("عدد", "units"),
            ),
            _text("deliveryCity", "شهر تحویل", "Delivery city", required=True, max_length=60),
        ),
    ),
    ServiceDefinition(
        id="vehicle-purchase",
        department=Department.VEHICLE,
        title=_l("درخواست خرید خودرو", "Vehicle purchase"),
        summary=_l(
            "ثبت درخواست خرید خودروی سواری یا تجاری",
            "Request a passenger or commercial vehicle",
        ),
        description=_l(
            "کارشناس خودرو درخواست شما را بررسی و گزینه‌های موجود را اعلام می‌کند.",
            "The vehicle team reviews your request and replies with available options.",
        ),
        requirements=(
            _l("نوع خودرو و سوخت موردنظر را مشخص کنید", "Choose the vehicle and fuel type"),
            _l("در صورت نیاز مدل ترجیحی را بنویسید", "Optionally note a preferred model"),
        ),
        eta_days=14,
        fields=(
            _select(
                "vehicleType",
                "نوع خودرو",
                "Vehicle type",
                [
                    _option("sedan", "سواری", "Sedan"),
                    _option("suv", "شاسی‌بلند", "SUV"),
                    _option("pickup", "وانت", "Pickup"),
                    _option("van", "ون", "Van"),
                ],
            ),
            _select(
                "fuelType",
                "نوع سوخت",
                "Fuel type",
                [
                    _option("gasoline", "بنزینی", "Gasoline"),
                    _option("hybrid", "هیبریدی", "Hybrid"),
                    _option("electric", "برقی", "Electric"),
                ],
            ),
            _text("preferredModel", "مدل ترجیحی", "Preferred model", required=False, max_length=60),
        ),
    ),
    ServiceDefinition(
        id="vehicle-maintenance",
        department=Department.VEHICLE,
        title=_l("خدمات و تعمیر خودرو", "Vehicle service & repair"),
        summary=_l("سرویس دوره‌ای، تعمیر و معاینه فنی", "Periodic service, repair and inspection"),
        description=_l(
            "کارشناس خودرو زمان مراجعه یا اعزام خدمات را با شما هماهنگ می‌کند.",
            "The vehicle team coordinates a service visit or appointment with you.",
        ),
        requirements=(
            _l("شماره پلاک خودرو را آماده کنید", "Have the licence plate ready"),
            _l("نوع خدمت موردنیاز را مشخص کنید", "Choose the type of service"),
        ),
        eta_days=3,
        fields=(
            _text("plate", "شماره پلاک", "Licence plate", required=True, max_length=12),
            _select(
                "serviceType",
                "نوع خدمت",
                "Service type",
                [
                    _option("periodic", "سرویس دوره‌ای", "Periodic service"),
                    _option("repair", "تعمیر", "Repair"),
                    _option("inspection", "معاینه فنی", "Inspection"),
                ],
            ),
        ),
    ),
    ServiceDefinition(
        id="housing-unit",
        department=Department.HOUSING,
        title=_l("درخواست واحد مسکونی", "Housing unit application"),
        summary=_l("ثبت‌نام برای دریافت واحد مسکونی", "Apply for a housing unit"),
        description=_l(
            "کارشناس مسکن شرایط خانوار شما را بررسی و نتیجه را اعلام می‌کند.",
            "The housing team reviews your household situation and posts the outcome.",
        ),
        requirements=(
            _l("تعداد اعضای خانوار را مشخص کنید", "Know your household size"),
            _l("شهر موردنظر را تعیین کنید", "Decide your preferred city"),
        ),
        eta_days=30,
        fields=(
            _select(
                "unitType",
                "نوع واحد",
                "Unit type",
                [
                    _option("apartment", "آپارتمان", "Apartment"),
                    _option("house", "ویلایی", "House"),
                    _option("studio", "استودیو", "Studio"),
                ],
            ),
            _number(
                "householdSize",
                "تعداد اعضای خانوار",
                "Household size",
                minimum=1,
                maximum=12,
                unit=_l("نفر", "people"),
            ),
            _text("preferredCity", "شهر موردنظر", "Preferred city", required=True, max_length=60),
        ),
    ),
    ServiceDefinition(
        id="rent-subsidy",
        department=Department.HOUSING,
        title=_l("کمک‌هزینه اجاره", "Rent support"),
        summary=_l(
            "کمک به پرداخت بخشی از اجاره‌بها",
            "Help covering part of your monthly rent",
        ),
        description=_l(
            "کارشناس مسکن مبلغ اجاره و تعداد اعضای خانوار را بررسی می‌کند و میزان کمک را اعلام می‌کند.",
            "The housing team reviews your rent and household size and confirms the support amount.",
        ),
        requirements=(
            _l("مبلغ اجاره ماهانه را آماده کنید", "Have your monthly rent amount ready"),
            _l("تعداد اعضای خانوار را مشخص کنید", "Know your household size"),
        ),
        eta_days=15,
        fields=(
            _number(
                "monthlyRent",
                "اجاره ماهانه",
                "Monthly rent",
                minimum=1_000_000,
                maximum=200_000_000,
                unit=_IRR,
            ),
            _number(
                "householdSize",
                "تعداد اعضای خانوار",
                "Household size",
                minimum=1,
                maximum=12,
                unit=_l("نفر", "people"),
            ),
        ),
    ),
)
