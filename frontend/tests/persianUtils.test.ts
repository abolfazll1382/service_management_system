import { describe, expect, it } from "vitest";
import { generateTrackingCode, isValidNationalId, normalizeDigits, toPersianDigits } from "@/lib/utils/persianUtils";
import { maskNationalId } from "@/lib/utils/mask";
import { withCheckDigit } from "./nationalId";

describe("isValidNationalId", () => {
  it("accepts the seeded demo IDs", () => {
    for (const id of ["0045813922", "1277348561", "0592846717"]) expect(isValidNationalId(id), id).toBe(true);
  });

  it("accepts codes generated with a correct check digit", () => {
    let checked = 0;
    for (let n = 0; n < 3000; n++) {
      const prefix = String(Math.floor(Math.random() * 1e9)).padStart(9, "0");
      const id = withCheckDigit(prefix);
      if (/^(\d)\1{9}$/.test(id)) continue; // repdigits are rejected on purpose
      expect(isValidNationalId(id), id).toBe(true);
      checked++;
    }
    expect(checked).toBeGreaterThan(2900);
  });

  it("rejects any code whose last digit is wrong", () => {
    for (let n = 0; n < 500; n++) {
      const valid = withCheckDigit(String(Math.floor(Math.random() * 1e9)).padStart(9, "0"));
      const wrong = (Number(valid[9]) + 1 + Math.floor(Math.random() * 9)) % 10; // any digit but the right one
      expect(isValidNationalId(`${valid.slice(0, 9)}${wrong}`), valid).toBe(false);
    }
  });

  it("rejects repeated digits, wrong lengths and non-digits", () => {
    for (const bad of ["1111111111", "0000000000", "004581392", "00458139222", "00458139a2", "", "۰۰۴۵۸۱۳۹۲۲"]) {
      expect(isValidNationalId(bad), bad).toBe(false);
    }
  });
});

describe("digit conversion", () => {
  it("round-trips ASCII ↔ Persian digits", () => {
    expect(toPersianDigits("0045813922")).toBe("۰۰۴۵۸۱۳۹۲۲");
    expect(normalizeDigits("۰۰۴۵۸۱۳۹۲۲")).toBe("0045813922");
    expect(toPersianDigits(1405)).toBe("۱۴۰۵");
  });

  it("normalises Arabic-Indic digits and leaves everything else alone", () => {
    expect(normalizeDigits("٠٩١٢٣٤٥٦٧٨٩")).toBe("09123456789");
    expect(normalizeDigits("abc ۱۲ 34")).toBe("abc 12 34");
  });
});

describe("generateTrackingCode", () => {
  it("is always exactly 10 digits", () => {
    for (let n = 0; n < 200; n++) expect(generateTrackingCode()).toMatch(/^\d{10}$/);
  });
});

describe("maskNationalId", () => {
  it("keeps the first three and last two digits", () => {
    expect(maskNationalId("0045813922")).toBe("004•••••22");
    expect(maskNationalId("0045813922")).toHaveLength(10);
  });

  it("never echoes a short value back", () => {
    expect(maskNationalId("123")).toBe("•••");
  });
});
