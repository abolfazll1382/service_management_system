/**
 * `crypto.randomUUID` only exists in secure contexts (HTTPS or localhost).
 * Opening the dev server from a phone over a LAN address (http://192.168…)
 * is NOT one, and would throw. `getRandomValues` works everywhere, so fall
 * back to building a v4-style id from it.
 */
export function createId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** 256 random bits as hex — the bearer token a (mock) session is keyed by. */
export function createToken(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}
