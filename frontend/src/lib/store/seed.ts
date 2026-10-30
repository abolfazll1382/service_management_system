import type { AuditEntry } from "@/types/audit";
import type { DepartmentId } from "@/types/department";
import { localizedFromPlain } from "@/types/i18n";
import type { RequestStatus, ServiceRequest, TimelineEvent } from "@/types/request";
import type { ServiceDetails } from "@/types/service";
import { toActorRef, type ActorRef, type StoredUser } from "@/types/user";

/** Every seeded account uses this password; the login pages say so. */
export const DEMO_PASSWORD = "Demo@1234";

export interface SessionRecord {
  userId: string;
  expiresAt: string;
}

export interface MockDbData {
  users: StoredUser[];
  requests: ServiceRequest[];
  /** serviceId → accepting requests. A missing key means "accepting". */
  serviceActive: Record<string, boolean>;
  sessions: Record<string, SessionRecord>;
  audit: AuditEntry[];
}

const CREATED = "2026-09-01T08:00:00.000Z";

/**
 * Password hashes are SHA-256(`${salt}:Demo@1234`) with a per-user salt,
 * precomputed so the seed stays synchronous. tests/seed.test.ts recomputes
 * each one, so a typo here fails CI instead of locking a demo account out.
 */
function seedUsers(): StoredUser[] {
  return [
    {
      id: "u-admin",
      role: "admin",
      username: "admin",
      name: { fa: "مدیر سامانه", en: "System Administrator" },
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-admin",
      passwordHash: "65bb29251f4288171aa600fdde335ababc779539fd018c4ffef9b47926b860b2",
    },
    {
      id: "u-reza",
      role: "staff",
      username: "reza",
      name: { fa: "رضا کریمی", en: "Reza Karimi" },
      departmentIds: ["loan"],
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-reza",
      passwordHash: "a17b4063033ce508a1992d113dcf2a3f7a3f045b17c33d188b99f8eb417e3180",
    },
    {
      id: "u-sara",
      role: "staff",
      username: "sara",
      name: { fa: "سارا محمدی", en: "Sara Mohammadi" },
      departmentIds: ["raw_material"],
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-sara",
      passwordHash: "7d36315eabd26a4685b67196f00e487a091cf6c997ffb36a3f41660fb7f73951",
    },
    {
      id: "u-ali",
      role: "staff",
      username: "ali",
      name: { fa: "علی رضایی", en: "Ali Rezaei" },
      departmentIds: ["vehicle"],
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-ali",
      passwordHash: "602167cbc50eedc42d0bd77e8c2c10e6a3fc1a61d3a484ba1ed6ce8cd8854344",
    },
    {
      id: "u-maryam",
      role: "staff",
      username: "maryam",
      name: { fa: "مریم حسینی", en: "Maryam Hosseini" },
      departmentIds: ["housing"],
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-maryam",
      passwordHash: "2980c2142a0f5bb4bb40fa176ddb1deb0b320cd03b52672e673cd0a208dcbec3",
    },
    {
      id: "c-amir",
      role: "customer",
      fullName: "امیر حسینی",
      nationalId: "0045813922",
      phone: "09121234567",
      postalCode: "1458943671",
      address: "تهران، خیابان ولیعصر، پلاک ۱۲",
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-amir",
      passwordHash: "12e4e61adfa3dc2be76606b3901295742197a7c48ded9b7fb8b96ce5e0c1e6b8",
    },
    {
      id: "c-maryam",
      role: "customer",
      fullName: "مریم احمدی",
      nationalId: "1277348561",
      phone: "09352345678",
      postalCode: "5166734829",
      address: "تبریز، خیابان شریعتی، پلاک ۷",
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-maryam-c",
      passwordHash: "4ad301a0e0fc61df237199686950cee3c1adb2be0affc0569aae1551bfb7ba57",
    },
    {
      id: "c-hossein",
      role: "customer",
      fullName: "Hossein Karimi",
      nationalId: "0592846717",
      phone: "09189876543",
      postalCode: "6134598217",
      address: "Isfahan, Naqsh-e Jahan Square, No. 3",
      isActive: true,
      createdAt: CREATED,
      passwordSalt: "seed-hossein",
      passwordHash: "a1a078057c6f22c66e52dc496ccb044657c3210a6e1486728358b9bc8c91e9f6",
    },
  ];
}

/* ------------------------------------------------------------------ */
/* Seed requests, built with a small helper so each reads as a story. */
/* ------------------------------------------------------------------ */

type Step =
  | { kind: "status"; to: RequestStatus; at: string; by: string }
  | { kind: "assign"; to: string | null; at: string; by: string }
  | { kind: "message"; visibility: "public" | "internal"; body: string; at: string; by: string };

interface SeedRequest {
  id: string;
  trackingCode: string;
  customerId: string;
  serviceId: string;
  departmentId: DepartmentId;
  description: string;
  details: ServiceDetails;
  submittedAt: string;
  steps: Step[];
}

function buildRequest(seed: SeedRequest, users: StoredUser[]): ServiceRequest {
  const byId = (id: string): ActorRef => {
    const user = users.find((candidate) => candidate.id === id);
    if (!user) throw new Error(`Seed references unknown user ${id}`);
    return toActorRef(user);
  };
  const customer = users.find((user) => user.id === seed.customerId);
  if (!customer || customer.role !== "customer") throw new Error(`Seed customer ${seed.customerId} missing`);

  const timeline: TimelineEvent[] = [
    { id: `${seed.id}-e0`, kind: "submitted", at: seed.submittedAt, actor: toActorRef(customer) },
  ];
  let status: RequestStatus = "pending_review";
  let assignee: ActorRef | null = null;
  let updatedAt = seed.submittedAt;

  seed.steps.forEach((step, index) => {
    const base = { id: `${seed.id}-e${index + 1}`, at: step.at, actor: byId(step.by) };
    updatedAt = step.at;
    if (step.kind === "status") {
      timeline.push({ ...base, kind: "status_changed", from: status, to: step.to });
      status = step.to;
    } else if (step.kind === "assign") {
      assignee = step.to ? byId(step.to) : null;
      timeline.push({ ...base, kind: "assigned", assignee });
    } else {
      timeline.push({ ...base, kind: "message", visibility: step.visibility, body: step.body });
    }
  });

  return {
    id: seed.id,
    trackingCode: seed.trackingCode,
    customerId: customer.id,
    customer: { fullName: customer.fullName, nationalId: customer.nationalId, phone: customer.phone },
    departmentId: seed.departmentId,
    serviceId: seed.serviceId,
    description: seed.description,
    details: seed.details,
    status,
    assignee,
    timeline,
    submittedAt: seed.submittedAt,
    updatedAt,
  };
}

const SEED_REQUESTS: SeedRequest[] = [
  {
    id: "req-seed-1",
    trackingCode: "4821093657",
    customerId: "c-amir",
    serviceId: "personal-loan",
    departmentId: "loan",
    description: "درخواست وام برای خرید لوازم منزل با اقساط ماهانه.",
    details: { amount: 150_000_000, termMonths: "24", purpose: "خرید لوازم منزل" },
    submittedAt: "2026-10-05T08:30:00.000Z",
    steps: [
      { kind: "assign", to: "u-reza", at: "2026-10-05T09:10:00.000Z", by: "u-reza" },
      { kind: "status", to: "in_progress", at: "2026-10-05T09:12:00.000Z", by: "u-reza" },
      {
        kind: "message",
        visibility: "public",
        body: "مدارک شما دریافت شد و در حال بررسی است. / Your documents were received and are under review.",
        at: "2026-10-05T09:20:00.000Z",
        by: "u-reza",
      },
    ],
  },
  {
    id: "req-seed-2",
    trackingCode: "7093845216",
    customerId: "c-amir",
    serviceId: "vehicle-purchase",
    departmentId: "vehicle",
    description: "به‌دنبال یک خودروی هیبریدی برای استفاده روزانه در شهر هستم.",
    details: { vehicleType: "sedan", fuelType: "hybrid" },
    submittedAt: "2026-10-11T14:05:00.000Z",
    steps: [],
  },
  {
    id: "req-seed-3",
    trackingCode: "3647182905",
    customerId: "c-maryam",
    serviceId: "steel-supply",
    departmentId: "raw_material",
    description: "میلگرد برای پروژه ساختمانی در تبریز، تحویل در سه مرحله.",
    details: { material: "rebar", quantity: 40, deliveryCity: "تبریز" },
    submittedAt: "2026-10-02T10:00:00.000Z",
    steps: [
      { kind: "assign", to: "u-sara", at: "2026-10-02T11:00:00.000Z", by: "u-sara" },
      { kind: "status", to: "in_progress", at: "2026-10-02T11:05:00.000Z", by: "u-sara" },
      {
        kind: "message",
        visibility: "public",
        body: "لطفاً شماره پروژه را اعلام کنید. / Please share the project number.",
        at: "2026-10-03T08:40:00.000Z",
        by: "u-sara",
      },
      { kind: "status", to: "needs_correction", at: "2026-10-03T08:41:00.000Z", by: "u-sara" },
    ],
  },
  {
    id: "req-seed-4",
    trackingCode: "1059382746",
    customerId: "c-maryam",
    serviceId: "housing-unit",
    departmentId: "housing",
    description: "خانوار چهارنفره هستیم و یک آپارتمان در تبریز نیاز داریم.",
    details: { unitType: "apartment", householdSize: 4, preferredCity: "تبریز" },
    submittedAt: "2026-09-20T09:15:00.000Z",
    steps: [
      { kind: "assign", to: "u-maryam", at: "2026-09-20T10:00:00.000Z", by: "u-maryam" },
      { kind: "status", to: "in_progress", at: "2026-09-20T10:05:00.000Z", by: "u-maryam" },
      {
        kind: "message",
        visibility: "internal",
        body: "Eligibility checked against the household register — looks fine.",
        at: "2026-09-27T12:00:00.000Z",
        by: "u-maryam",
      },
      { kind: "status", to: "approved", at: "2026-09-28T12:30:00.000Z", by: "u-maryam" },
    ],
  },
  {
    id: "req-seed-5",
    trackingCode: "8273641950",
    customerId: "c-hossein",
    serviceId: "business-loan",
    departmentId: "loan",
    description: "Working capital to buy a second corrugator for our packaging workshop.",
    details: { amount: 800_000_000, termMonths: "36", businessField: "Packaging manufacturing" },
    submittedAt: "2026-10-12T07:45:00.000Z",
    steps: [],
  },
  {
    id: "req-seed-6",
    trackingCode: "2916485073",
    customerId: "c-hossein",
    serviceId: "packaging-supply",
    departmentId: "raw_material",
    description: "Monthly cardboard stock for the workshop.",
    details: { material: "cardboard", quantity: 5000, deliveryCity: "Isfahan" },
    submittedAt: "2026-09-10T08:00:00.000Z",
    steps: [
      { kind: "assign", to: "u-sara", at: "2026-09-10T09:00:00.000Z", by: "u-sara" },
      { kind: "status", to: "in_progress", at: "2026-09-10T09:02:00.000Z", by: "u-sara" },
      { kind: "status", to: "approved", at: "2026-09-12T10:00:00.000Z", by: "u-sara" },
      { kind: "status", to: "closed", at: "2026-09-20T10:00:00.000Z", by: "u-sara" },
    ],
  },
  {
    id: "req-seed-7",
    trackingCode: "6350174829",
    customerId: "c-amir",
    serviceId: "rent-subsidy",
    departmentId: "housing",
    description: "اجاره ماهانه خانه ما امسال افزایش یافته است.",
    details: { monthlyRent: 12_000_000, householdSize: 3 },
    submittedAt: "2026-10-08T16:20:00.000Z",
    steps: [
      { kind: "assign", to: "u-maryam", at: "2026-10-09T08:00:00.000Z", by: "u-maryam" },
      { kind: "status", to: "in_progress", at: "2026-10-09T08:03:00.000Z", by: "u-maryam" },
    ],
  },
  {
    id: "req-seed-8",
    trackingCode: "5184730962",
    customerId: "c-hossein",
    serviceId: "vehicle-maintenance",
    departmentId: "vehicle",
    description: "Periodic service for the delivery van.",
    details: { plate: "12B34567", serviceType: "periodic" },
    submittedAt: "2026-10-06T11:10:00.000Z",
    steps: [
      { kind: "assign", to: "u-ali", at: "2026-10-06T12:00:00.000Z", by: "u-ali" },
      { kind: "status", to: "in_progress", at: "2026-10-06T12:02:00.000Z", by: "u-ali" },
      {
        kind: "message",
        visibility: "public",
        body: "ظرفیت این ماه تکمیل است. / Service slots are full this month.",
        at: "2026-10-07T09:00:00.000Z",
        by: "u-ali",
      },
      { kind: "status", to: "rejected", at: "2026-10-07T09:01:00.000Z", by: "u-ali" },
    ],
  },
];

/** A fresh copy every call, so resetting never shares references with live state. */
export function createSeedData(): MockDbData {
  const users = seedUsers();
  return {
    users,
    requests: SEED_REQUESTS.map((seed) => buildRequest(seed, users)),
    serviceActive: {},
    sessions: {},
    audit: [],
  };
}

export { localizedFromPlain };
