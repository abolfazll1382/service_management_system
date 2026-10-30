import { normalizeDigits } from "./persianUtils";

/**
 * For react-hook-form's `setValueAs` on IDs and phone numbers: accepts the
 * digits in any script and forgives spaces and hyphens ("0912 123-4567").
 * Validation then always sees plain ASCII while the box keeps showing what
 * the person typed.
 */
export const asDigits = (value: string): string => normalizeDigits(value).replace(/[\s-]/g, "");

/** Same idea for amounts: "۱۵۰٬۰۰۰" or "150,000" → 150000; blank stays undefined so "required" fires. */
export function asNumber(value: string): number | undefined {
  const cleaned = normalizeDigits(value).replace(/[\s,٬،]/g, "");
  return cleaned === "" ? undefined : Number(cleaned);
}
