/**
 * Persian-locale helpers: National ID checksum, digit conversion and a mock
 * tracking-code generator. Date and number formatting that depends on the
 * ACTIVE language lives in lib/i18n/format.ts instead.
 *
 * These are structural helpers only. `isValidNationalId` confirms a number is
 * WELL-FORMED (public modulo-11 checksum); it cannot confirm the number is
 * assigned to anyone — that would need a real registry this demo does not
 * have, and the UI never claims otherwise.
 */

/**
 * Validates an Iranian National ID (کد ملی): the first 9 digits are weighted
 * 10…2, summed and reduced mod 11; that remainder decides the 10th digit.
 * Covered by tests/persianUtils.test.ts with generated valid/invalid codes.
 */
export function isValidNationalId(value: string): boolean {
  if (!/^\d{10}$/.test(value)) return false;

  // "1111111111" passes the arithmetic for some digits but is never issued.
  if (/^(\d)\1{9}$/.test(value)) return false;

  const digits = value.split("").map(Number);
  const checkDigit = digits[9];

  const weightedSum = digits.slice(0, 9).reduce((sum, digit, index) => sum + digit * (10 - index), 0);
  const remainder = weightedSum % 11;

  return remainder < 2 ? checkDigit === remainder : checkDigit === 11 - remainder;
}

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"] as const;

/**
 * ASCII → Persian digits. Display-only: form values, ids and storage keys
 * stay ASCII so validation and comparisons stay trivial.
 */
export function toPersianDigits(value: string | number): string {
  return String(value).replace(/[0-9]/g, (digit) => PERSIAN_DIGITS[Number(digit)]);
}

/**
 * Persian (۰-۹) and Arabic-Indic (٠-٩) digits → ASCII. Persian users
 * routinely type digits in their own script, and a regex like /^\d{10}$/
 * would reject "۰۰۴۵۸۱۳۹۲۲" outright. Applied as the form field's
 * `setValueAs`, so validation always sees ASCII while the box keeps showing
 * what the person typed.
 */
export function normalizeDigits(value: string): string {
  return value
    .replace(/[۰-۹]/g, (digit) => String(digit.charCodeAt(0) - 0x06f0))
    .replace(/[٠-٩]/g, (digit) => String(digit.charCodeAt(0) - 0x0660));
}

/**
 * Mock tracking code: 10 random digits. A real backend issues these
 * server-side with a uniqueness guarantee; the mock server re-rolls on
 * collision (lib/mock-server/requests.ts).
 */
export function generateTrackingCode(): string {
  return Array.from({ length: 10 }, () => Math.floor(Math.random() * 10)).join("");
}

/**
 * The inverse of `isValidNationalId`: given the first nine digits, appends
 * the check digit. For demo/sample data only — it manufactures a WELL-FORMED
 * number, which says nothing about whether anyone holds it.
 */
export function completeNationalId(firstNine: string): string {
  if (!/^\d{9}$/.test(firstNine)) throw new Error("Expected exactly nine digits");
  const sum = firstNine.split("").reduce((total, digit, index) => total + Number(digit) * (10 - index), 0);
  const remainder = sum % 11;
  const completed = `${firstNine}${remainder < 2 ? remainder : 11 - remainder}`;
  // A repdigit such as 0000000000 passes the arithmetic but is never issued; nudge it.
  return /^(\d)\1{9}$/.test(completed) ? completeNationalId(`${(Number(firstNine[0]) + 1) % 10}${firstNine.slice(1)}`) : completed;
}
