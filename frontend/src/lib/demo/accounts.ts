import type { DepartmentId } from "@/types/department";
import type { Localized } from "@/types/i18n";
import { createSeedData, DEMO_PASSWORD } from "@/lib/store/seed";
import { completeNationalId } from "@/lib/utils/persianUtils";

/**
 * What the sign-in pages show in their "Demo accounts" box. Derived from the
 * same seed the mock server starts from, so the list can't drift from the
 * accounts that actually exist.
 */
export { DEMO_PASSWORD };

export interface DemoCustomer {
  name: string;
  nationalId: string;
}

export interface DemoStaff {
  name: Localized;
  username: string;
  role: "admin" | "staff";
  departmentIds: readonly DepartmentId[];
}

const seed = createSeedData();

export const DEMO_CUSTOMERS: readonly DemoCustomer[] = seed.users.flatMap((user) =>
  user.role === "customer" ? [{ name: user.fullName, nationalId: user.nationalId }] : [],
);

export const DEMO_STAFF: readonly DemoStaff[] = seed.users.flatMap((user) =>
  user.role === "customer"
    ? []
    : [{ name: user.name, username: user.username, role: user.role, departmentIds: user.role === "staff" ? user.departmentIds : [] }],
);

const randomDigits = (count: number) => Array.from({ length: count }, () => Math.floor(Math.random() * 10)).join("");

/**
 * Plausible, well-formed registration details for trying the flow without
 * inventing a checksum-valid National ID by hand. Random on every call, and
 * obviously fictional (generic name and address).
 */
export function createSampleRegistration(locale: "fa" | "en") {
  return {
    fullName: locale === "fa" ? "شهروند نمونه" : "Sample Citizen",
    nationalId: completeNationalId(randomDigits(9)),
    phone: `09${randomDigits(9)}`,
    postalCode: randomDigits(10),
    address: locale === "fa" ? "تهران، خیابان نمونه، پلاک ۱" : "Tehran, Sample Street, No. 1",
    password: DEMO_PASSWORD,
  };
}
