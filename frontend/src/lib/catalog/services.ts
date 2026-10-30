import type { Service } from "@/types/service";
import { toPersianDigits } from "@/lib/utils/persianUtils";

const MONTHS = (count: number) => ({
  value: String(count),
  label: { fa: `${toPersianDigits(count)} ماه`, en: `${count} months` },
});

/**
 * The service catalog is plain data. Each service lists the extra fields it
 * needs, and the apply wizard, the Zod schema and the staff work panel are all
 * derived from that list — so a new service is one entry here, no new UI.
 */
export const SERVICES: readonly Service[] = [
  {
    id: "personal-loan",
    departmentId: "loan",
    title: { fa: "وام شخصی", en: "Personal loan" },
    summary: {
      fa: "تأمین مالی نیازهای شخصی با اقساط ماهانه",
      en: "Finance personal needs with monthly installments",
    },
    description: {
      fa: "پس از ثبت درخواست، کارشناس تسهیلات مبلغ و مدت بازپرداخت موردنظر شما را بررسی می‌کند و نتیجه را از همین‌جا اعلام می‌کند.",
      en: "After you submit, a loan officer reviews the amount and repayment term you ask for and posts the outcome here.",
    },
    requirements: [
      { fa: "مبلغ و مدت بازپرداخت موردنظر را تعیین کنید", en: "Decide the amount and repayment term" },
      { fa: "هدف از دریافت وام را به‌طور خلاصه بنویسید", en: "Prepare a short note on what the loan is for" },
    ],
    etaDays: 5,
    fields: [
      {
        kind: "number",
        key: "amount",
        label: { fa: "مبلغ درخواستی", en: "Requested amount" },
        required: true,
        min: 10_000_000,
        max: 1_000_000_000,
        unit: { fa: "ریال", en: "IRR" },
      },
      {
        kind: "select",
        key: "termMonths",
        label: { fa: "مدت بازپرداخت", en: "Repayment term" },
        required: true,
        options: [MONTHS(12), MONTHS(24), MONTHS(36), MONTHS(48)],
      },
      {
        kind: "text",
        key: "purpose",
        label: { fa: "هدف از دریافت وام", en: "Purpose" },
        required: true,
        maxLength: 120,
      },
    ],
  },
  {
    id: "business-loan",
    departmentId: "loan",
    title: { fa: "تسهیلات کسب‌وکار", en: "Business loan" },
    summary: { fa: "سرمایه در گردش و توسعه کسب‌وکار", en: "Working capital and growth financing" },
    description: {
      fa: "کارشناس تسهیلات نیاز مالی کسب‌وکار شما را بررسی می‌کند و در صورت نیاز مدارک تکمیلی می‌خواهد.",
      en: "A loan officer reviews your business financing need and asks for supporting documents if required.",
    },
    requirements: [
      { fa: "حوزه فعالیت کسب‌وکار را مشخص کنید", en: "Know your business field" },
      { fa: "برآورد مبلغ موردنیاز را آماده کنید", en: "Prepare an estimate of the amount you need" },
    ],
    etaDays: 10,
    fields: [
      {
        kind: "number",
        key: "amount",
        label: { fa: "مبلغ درخواستی", en: "Requested amount" },
        required: true,
        min: 50_000_000,
        max: 5_000_000_000,
        unit: { fa: "ریال", en: "IRR" },
      },
      {
        kind: "select",
        key: "termMonths",
        label: { fa: "مدت بازپرداخت", en: "Repayment term" },
        required: true,
        options: [MONTHS(12), MONTHS(24), MONTHS(36), MONTHS(60)],
      },
      {
        kind: "text",
        key: "businessField",
        label: { fa: "حوزه فعالیت", en: "Business field" },
        required: true,
        maxLength: 80,
      },
    ],
  },
  {
    id: "steel-supply",
    departmentId: "raw_material",
    title: { fa: "تأمین فولاد", en: "Steel supply" },
    summary: {
      fa: "ورق، میلگرد و پروفیل برای پروژه‌های تولیدی",
      en: "Sheet, rebar and profiles for production",
    },
    description: {
      fa: "درخواست تأمین فولاد به کارشناس مواد اولیه ارجاع می‌شود تا موجودی و زمان تحویل را اعلام کند.",
      en: "Your steel request goes to the raw-materials team, who confirm stock and delivery time.",
    },
    requirements: [
      { fa: "نوع فولاد و مقدار موردنیاز را مشخص کنید", en: "Know the steel type and quantity" },
      { fa: "شهر تحویل را اعلام کنید", en: "Decide the delivery city" },
    ],
    etaDays: 7,
    fields: [
      {
        kind: "select",
        key: "material",
        label: { fa: "نوع فولاد", en: "Steel type" },
        required: true,
        options: [
          { value: "sheet", label: { fa: "ورق", en: "Sheet" } },
          { value: "rebar", label: { fa: "میلگرد", en: "Rebar" } },
          { value: "profile", label: { fa: "پروفیل", en: "Profile" } },
        ],
      },
      {
        kind: "number",
        key: "quantity",
        label: { fa: "مقدار", en: "Quantity" },
        required: true,
        min: 1,
        max: 500,
        unit: { fa: "تن", en: "tons" },
      },
      {
        kind: "text",
        key: "deliveryCity",
        label: { fa: "شهر تحویل", en: "Delivery city" },
        required: true,
        maxLength: 60,
      },
    ],
  },
  {
    id: "packaging-supply",
    departmentId: "raw_material",
    title: { fa: "تأمین مواد بسته‌بندی", en: "Packaging supply" },
    summary: {
      fa: "کارتن، پلاستیک و شیشه برای بسته‌بندی محصول",
      en: "Cardboard, plastic and glass for product packaging",
    },
    description: {
      fa: "کارشناس مواد اولیه درخواست شما را بررسی و زمان تأمین را اعلام می‌کند.",
      en: "The raw-materials team reviews your request and confirms the supply time.",
    },
    requirements: [
      { fa: "نوع ماده و تعداد موردنیاز را مشخص کنید", en: "Know the material type and quantity" },
      { fa: "شهر تحویل را اعلام کنید", en: "Decide the delivery city" },
    ],
    etaDays: 5,
    fields: [
      {
        kind: "select",
        key: "material",
        label: { fa: "نوع ماده", en: "Material" },
        required: true,
        options: [
          { value: "cardboard", label: { fa: "کارتن", en: "Cardboard" } },
          { value: "plastic", label: { fa: "پلاستیک", en: "Plastic" } },
          { value: "glass", label: { fa: "شیشه", en: "Glass" } },
        ],
      },
      {
        kind: "number",
        key: "quantity",
        label: { fa: "تعداد", en: "Quantity" },
        required: true,
        min: 100,
        max: 1_000_000,
        unit: { fa: "عدد", en: "units" },
      },
      {
        kind: "text",
        key: "deliveryCity",
        label: { fa: "شهر تحویل", en: "Delivery city" },
        required: true,
        maxLength: 60,
      },
    ],
  },
  {
    id: "vehicle-purchase",
    departmentId: "vehicle",
    title: { fa: "درخواست خرید خودرو", en: "Vehicle purchase" },
    summary: {
      fa: "ثبت درخواست خرید خودروی سواری یا تجاری",
      en: "Request a passenger or commercial vehicle",
    },
    description: {
      fa: "کارشناس خودرو درخواست شما را بررسی و گزینه‌های موجود را اعلام می‌کند.",
      en: "The vehicle team reviews your request and replies with available options.",
    },
    requirements: [
      { fa: "نوع خودرو و سوخت موردنظر را مشخص کنید", en: "Choose the vehicle and fuel type" },
      { fa: "در صورت نیاز مدل ترجیحی را بنویسید", en: "Optionally note a preferred model" },
    ],
    etaDays: 14,
    fields: [
      {
        kind: "select",
        key: "vehicleType",
        label: { fa: "نوع خودرو", en: "Vehicle type" },
        required: true,
        options: [
          { value: "sedan", label: { fa: "سواری", en: "Sedan" } },
          { value: "suv", label: { fa: "شاسی‌بلند", en: "SUV" } },
          { value: "pickup", label: { fa: "وانت", en: "Pickup" } },
          { value: "van", label: { fa: "ون", en: "Van" } },
        ],
      },
      {
        kind: "select",
        key: "fuelType",
        label: { fa: "نوع سوخت", en: "Fuel type" },
        required: true,
        options: [
          { value: "gasoline", label: { fa: "بنزینی", en: "Gasoline" } },
          { value: "hybrid", label: { fa: "هیبریدی", en: "Hybrid" } },
          { value: "electric", label: { fa: "برقی", en: "Electric" } },
        ],
      },
      {
        kind: "text",
        key: "preferredModel",
        label: { fa: "مدل ترجیحی", en: "Preferred model" },
        required: false,
        maxLength: 60,
      },
    ],
  },
  {
    id: "vehicle-maintenance",
    departmentId: "vehicle",
    title: { fa: "خدمات و تعمیر خودرو", en: "Vehicle service & repair" },
    summary: { fa: "سرویس دوره‌ای، تعمیر و معاینه فنی", en: "Periodic service, repair and inspection" },
    description: {
      fa: "کارشناس خودرو زمان مراجعه یا اعزام خدمات را با شما هماهنگ می‌کند.",
      en: "The vehicle team coordinates a service visit or appointment with you.",
    },
    requirements: [
      { fa: "شماره پلاک خودرو را آماده کنید", en: "Have the licence plate ready" },
      { fa: "نوع خدمت موردنیاز را مشخص کنید", en: "Choose the type of service" },
    ],
    etaDays: 3,
    fields: [
      {
        kind: "text",
        key: "plate",
        label: { fa: "شماره پلاک", en: "Licence plate" },
        required: true,
        maxLength: 12,
      },
      {
        kind: "select",
        key: "serviceType",
        label: { fa: "نوع خدمت", en: "Service type" },
        required: true,
        options: [
          { value: "periodic", label: { fa: "سرویس دوره‌ای", en: "Periodic service" } },
          { value: "repair", label: { fa: "تعمیر", en: "Repair" } },
          { value: "inspection", label: { fa: "معاینه فنی", en: "Inspection" } },
        ],
      },
    ],
  },
  {
    id: "housing-unit",
    departmentId: "housing",
    title: { fa: "درخواست واحد مسکونی", en: "Housing unit application" },
    summary: { fa: "ثبت‌نام برای دریافت واحد مسکونی", en: "Apply for a housing unit" },
    description: {
      fa: "کارشناس مسکن شرایط خانوار شما را بررسی و نتیجه را اعلام می‌کند.",
      en: "The housing team reviews your household situation and posts the outcome.",
    },
    requirements: [
      { fa: "تعداد اعضای خانوار را مشخص کنید", en: "Know your household size" },
      { fa: "شهر موردنظر را تعیین کنید", en: "Decide your preferred city" },
    ],
    etaDays: 30,
    fields: [
      {
        kind: "select",
        key: "unitType",
        label: { fa: "نوع واحد", en: "Unit type" },
        required: true,
        options: [
          { value: "apartment", label: { fa: "آپارتمان", en: "Apartment" } },
          { value: "house", label: { fa: "ویلایی", en: "House" } },
          { value: "studio", label: { fa: "استودیو", en: "Studio" } },
        ],
      },
      {
        kind: "number",
        key: "householdSize",
        label: { fa: "تعداد اعضای خانوار", en: "Household size" },
        required: true,
        min: 1,
        max: 12,
        unit: { fa: "نفر", en: "people" },
      },
      {
        kind: "text",
        key: "preferredCity",
        label: { fa: "شهر موردنظر", en: "Preferred city" },
        required: true,
        maxLength: 60,
      },
    ],
  },
  {
    id: "rent-subsidy",
    departmentId: "housing",
    title: { fa: "کمک‌هزینه اجاره", en: "Rent support" },
    summary: {
      fa: "کمک به پرداخت بخشی از اجاره‌بها",
      en: "Help covering part of your monthly rent",
    },
    description: {
      fa: "کارشناس مسکن مبلغ اجاره و تعداد اعضای خانوار را بررسی می‌کند و میزان کمک را اعلام می‌کند.",
      en: "The housing team reviews your rent and household size and confirms the support amount.",
    },
    requirements: [
      { fa: "مبلغ اجاره ماهانه را آماده کنید", en: "Have your monthly rent amount ready" },
      { fa: "تعداد اعضای خانوار را مشخص کنید", en: "Know your household size" },
    ],
    etaDays: 15,
    fields: [
      {
        kind: "number",
        key: "monthlyRent",
        label: { fa: "اجاره ماهانه", en: "Monthly rent" },
        required: true,
        min: 1_000_000,
        max: 200_000_000,
        unit: { fa: "ریال", en: "IRR" },
      },
      {
        kind: "number",
        key: "householdSize",
        label: { fa: "تعداد اعضای خانوار", en: "Household size" },
        required: true,
        min: 1,
        max: 12,
        unit: { fa: "نفر", en: "people" },
      },
    ],
  },
];
