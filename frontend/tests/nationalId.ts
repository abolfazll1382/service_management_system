/** Builds a checksum-valid national ID from a 9-digit prefix. */
export function withCheckDigit(prefix: string): string {
  const sum = prefix.split("").reduce((total, digit, index) => total + Number(digit) * (10 - index), 0);
  const remainder = sum % 11;
  return `${prefix}${remainder < 2 ? remainder : 11 - remainder}`;
}
