/**
 * Keeps the first three and last two digits ("0045813922" → "004•••••22").
 * Enough for a staff member to tell two applicants apart in a table, without
 * putting the full national ID on screen or into the audit log.
 */
export function maskNationalId(value: string): string {
  if (value.length < 6) return "•".repeat(value.length);
  return `${value.slice(0, 3)}${"•".repeat(value.length - 5)}${value.slice(-2)}`;
}
