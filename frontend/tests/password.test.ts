import { createHash, randomBytes } from "node:crypto";
import { describe, expect, it } from "vitest";
import { generateSalt, hashPassword, sha256Hex, verifyPassword } from "@/lib/auth/password";

const reference = (input: string) => createHash("sha256").update(input, "utf8").digest("hex");

describe("sha256Hex (pure TypeScript) matches node:crypto", () => {
  it("matches the published test vectors", () => {
    expect(sha256Hex("")).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    expect(sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("matches node:crypto across padding boundaries (0–200 bytes) and unicode", () => {
    for (let length = 0; length <= 200; length++) {
      const input = "x".repeat(length);
      expect(sha256Hex(input)).toBe(reference(input));
    }
    for (const input of ["رمز عبور ۱۲۳", "Demo@1234", "emoji 🔐", randomBytes(300).toString("base64")]) {
      expect(sha256Hex(input)).toBe(reference(input));
    }
  });
});

describe("password helpers", () => {
  it("verifies only the right password for a salt", () => {
    const salt = generateSalt();
    const hash = hashPassword("Demo@1234", salt);
    expect(verifyPassword("Demo@1234", salt, hash)).toBe(true);
    expect(verifyPassword("demo@1234", salt, hash)).toBe(false);
    expect(verifyPassword("Demo@1234", generateSalt(), hash)).toBe(false);
  });

  it("generates distinct salts", () => {
    expect(generateSalt()).not.toBe(generateSalt());
  });
});
