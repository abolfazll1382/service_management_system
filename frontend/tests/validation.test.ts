import { describe, expect, it } from "vitest";
import { createCustomerLoginSchema, createRegisterSchema, createRegisterInputSchema } from "@/lib/validation/auth";
import { createApplyFormSchema, createDetailsSchema, createTransitionSchema, toServiceDetails } from "@/lib/validation/request";
import { createStaffInputSchema } from "@/lib/validation/staff";
import { identityTranslate } from "@/lib/validation/fields";
import { createTranslator } from "@/lib/i18n/translate";
import { findService } from "@/lib/catalog";
import { withCheckDigit } from "./nationalId";

const t = identityTranslate;
const validRegistration = {
  fullName: "Nima Ahmadi",
  nationalId: withCheckDigit("123456789"),
  phone: "09151112233",
  postalCode: "1234567890",
  address: "Mashhad, Sajjad Blvd, No. 4",
  password: "Strong1pass",
};
const issuesFor = (result: { success: boolean; error?: { issues: { path: PropertyKey[]; message: string }[] } }) =>
  result.success ? [] : (result.error?.issues ?? []);

describe("registration schema", () => {
  const schema = createRegisterSchema(t);
  const form = { ...validRegistration, confirmPassword: "Strong1pass", acceptTerms: true };

  it("accepts a complete, valid form", () => {
    expect(schema.safeParse(form).success).toBe(true);
  });

  it.each([
    ["fullName", { fullName: "A" }],
    ["nationalId", { nationalId: "123" }],
    ["nationalId", { nationalId: "1234567890" }], // right length, wrong checksum
    ["phone", { phone: "08151112233" }],
    ["postalCode", { postalCode: "123" }],
    ["address", { address: "x" }],
    ["password", { password: "short1", confirmPassword: "short1" }],
    ["password", { password: "onlyletters", confirmPassword: "onlyletters" }],
    ["password", { password: "12345678", confirmPassword: "12345678" }],
    ["confirmPassword", { confirmPassword: "Different1pass" }],
    ["acceptTerms", { acceptTerms: false }],
  ])("flags %s when it is invalid", (field, override) => {
    const issues = issuesFor(schema.safeParse({ ...form, ...override }));
    expect(issues.map((issue) => issue.path[0])).toContain(field);
  });

  it("reports a missing field with the translated 'required' message, not Zod's English", () => {
    const tFa = createTranslator("fa");
    const issues = issuesFor(createRegisterInputSchema(tFa).safeParse({}));
    expect(issues.length).toBeGreaterThan(0);
    for (const issue of issues) expect(issue.message).toBe(tFa("validation.required"));
  });

  it("produces messages in the active language", () => {
    const en = issuesFor(createRegisterInputSchema(createTranslator("en")).safeParse({ ...validRegistration, phone: "1" }));
    const fa = issuesFor(createRegisterInputSchema(createTranslator("fa")).safeParse({ ...validRegistration, phone: "1" }));
    expect(en[0].message).toBe(createTranslator("en")("validation.phone"));
    expect(fa[0].message).toBe(createTranslator("fa")("validation.phone"));
    expect(en[0].message).not.toBe(fa[0].message);
  });
});

describe("login schema", () => {
  it("checks shape only, so an invalid-looking ID gets the generic credentials error later", () => {
    const schema = createCustomerLoginSchema(t);
    expect(schema.safeParse({ nationalId: "1234567890", password: "x" }).success).toBe(true); // bad checksum is fine here
    expect(schema.safeParse({ nationalId: "123", password: "x" }).success).toBe(false);
    expect(schema.safeParse({ nationalId: "1234567890", password: "" }).success).toBe(false);
  });
});

describe("service detail schema", () => {
  const loan = findService("personal-loan")!;
  const ok = { amount: 50_000_000, termMonths: "24", purpose: "Home appliances" };

  it("accepts valid details and strips unknown keys", () => {
    const parsed = createDetailsSchema(loan.fields, t).parse({ ...ok, extra: "ignored" });
    expect(parsed).toEqual(ok);
    expect(toServiceDetails(loan.fields, parsed)).toEqual(ok);
  });

  it("enforces numeric bounds, select options and required text", () => {
    const schema = createDetailsSchema(loan.fields, t);
    expect(schema.safeParse({ ...ok, amount: 1 }).success).toBe(false);
    expect(schema.safeParse({ ...ok, amount: 5_000_000_000 }).success).toBe(false);
    expect(schema.safeParse({ ...ok, amount: "50000000" }).success).toBe(false); // a string is not a number
    expect(schema.safeParse({ ...ok, termMonths: "13" }).success).toBe(false);
    expect(schema.safeParse({ ...ok, purpose: "   " }).success).toBe(false);
    expect(schema.safeParse({ ...ok, purpose: "x".repeat(121) }).success).toBe(false);
  });

  it("lets optional fields be left out", () => {
    const service = findService("vehicle-maintenance")!;
    const optional = service.fields.filter((field) => !field.required);
    if (optional.length === 0) return;
    const required = Object.fromEntries(
      service.fields
        .filter((field) => field.required)
        .map((field) => [field.key, field.kind === "select" ? field.options[0].value : field.kind === "number" ? field.min : "ABC"]),
    );
    expect(createDetailsSchema(service.fields, t).safeParse(required).success).toBe(true);
  });

  it("builds the whole apply form from the service definition", () => {
    const schema = createApplyFormSchema(loan, t);
    const valid = { description: "A sufficiently long description.", details: ok, confirm: true };
    expect(schema.safeParse(valid).success).toBe(true);
    expect(schema.safeParse({ ...valid, confirm: false }).success).toBe(false);
    expect(schema.safeParse({ ...valid, description: "short" }).success).toBe(false);
    expect(schema.safeParse({ ...valid, details: { ...ok, amount: 1 } }).success).toBe(false);
  });
});

describe("status-change schema", () => {
  const schema = createTransitionSchema(t);

  it("lets ordinary moves go through with or without a note", () => {
    expect(schema.safeParse({ to: "in_progress" }).success).toBe(true);
    expect(schema.safeParse({ to: "approved", note: "Done." }).success).toBe(true);
    expect(schema.safeParse({ to: "closed", note: "" }).success).toBe(true);
  });

  it("requires a note for rejection and for correction requests", () => {
    for (const to of ["rejected", "needs_correction"]) {
      expect(schema.safeParse({ to }).success, to).toBe(false);
      expect(schema.safeParse({ to, note: "  " }).success, to).toBe(false);
      expect(issuesFor(schema.safeParse({ to }))[0].path).toEqual(["note"]);
      expect(schema.safeParse({ to, note: "Because." }).success, to).toBe(true);
    }
  });

  it("rejects unknown statuses", () => {
    expect(schema.safeParse({ to: "teleported" }).success).toBe(false);
  });
});

describe("staff schema", () => {
  const schema = createStaffInputSchema(t);
  const ok = { nameFa: "نیما", nameEn: "Nima", username: "nima_1", password: "Welcome1pass", departmentIds: ["loan"] };

  it("accepts a valid new staff member", () => expect(schema.safeParse(ok).success).toBe(true));

  it("rejects bad usernames, missing translations, unknown or empty departments", () => {
    for (const bad of [
      { username: "Nima" },
      { username: "1nima" },
      { username: "ni" },
      { nameFa: "" },
      { nameEn: "N" },
      { departmentIds: [] },
      { departmentIds: ["space_travel"] },
    ]) {
      expect(schema.safeParse({ ...ok, ...bad }).success, JSON.stringify(bad)).toBe(false);
    }
  });
});
