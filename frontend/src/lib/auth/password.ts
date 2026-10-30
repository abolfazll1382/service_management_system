/**
 * DEMO-ONLY password handling for the mock server.
 *
 * A real backend hashes with a slow, salted algorithm (argon2id or bcrypt) on
 * the SERVER; the browser never sees a hash. This exists so the demo's
 * "database" holds salted digests instead of plaintext passwords, and so the
 * login flow has the right shape (look up user → verify → issue token).
 *
 * SHA-256 is implemented here in plain TypeScript rather than via
 * `crypto.subtle` because SubtleCrypto is unavailable on insecure origins —
 * opening the dev server from a phone over http://192.168… would break login.
 * tests/password.test.ts checks this implementation against node:crypto.
 */

function firstPrimes(count: number): number[] {
  const primes: number[] = [];
  for (let candidate = 2; primes.length < count; candidate++) {
    if (primes.every((prime) => candidate % prime !== 0)) primes.push(candidate);
  }
  return primes;
}

const fractionalBits = (value: number) => Math.floor((value - Math.floor(value)) * 2 ** 32);

const PRIMES = firstPrimes(64);
/** SHA-256 round constants: fractional parts of the cube roots of the first 64 primes. */
const K = PRIMES.map((prime) => fractionalBits(Math.cbrt(prime)));
/** Initial state: fractional parts of the square roots of the first 8 primes. */
const H0 = PRIMES.slice(0, 8).map((prime) => fractionalBits(Math.sqrt(prime)));

const rotr = (value: number, bits: number) => (value >>> bits) | (value << (32 - bits));

export function sha256Hex(input: string): string {
  const message = new TextEncoder().encode(input);
  const paddedLength = ((message.length + 9 + 63) >> 6) << 6;
  const padded = new Uint8Array(paddedLength);
  padded.set(message);
  padded[message.length] = 0x80;

  const view = new DataView(padded.buffer);
  const bitLength = message.length * 8;
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 2 ** 32));
  view.setUint32(paddedLength - 4, bitLength >>> 0);

  const state = Uint32Array.from(H0);
  const schedule = new Uint32Array(64);

  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let i = 0; i < 16; i++) schedule[i] = view.getUint32(offset + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(schedule[i - 15], 7) ^ rotr(schedule[i - 15], 18) ^ (schedule[i - 15] >>> 3);
      const s1 = rotr(schedule[i - 2], 17) ^ rotr(schedule[i - 2], 19) ^ (schedule[i - 2] >>> 10);
      schedule[i] = (schedule[i - 16] + s0 + schedule[i - 7] + s1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = state;
    for (let i = 0; i < 64; i++) {
      const sigma1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const choice = (e & f) ^ (~e & g);
      const temp1 = (h + sigma1 + choice + K[i] + schedule[i]) >>> 0;
      const sigma0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (sigma0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + temp1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) >>> 0;
    }

    const next = [a, b, c, d, e, f, g, h];
    for (let i = 0; i < 8; i++) state[i] = (state[i] + next[i]) >>> 0;
  }

  return Array.from(state, (word) => word.toString(16).padStart(8, "0")).join("");
}

export function generateSalt(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function hashPassword(password: string, salt: string): string {
  return sha256Hex(`${salt}:${password}`);
}

export function verifyPassword(password: string, salt: string, expectedHash: string): boolean {
  return hashPassword(password, salt) === expectedHash;
}
