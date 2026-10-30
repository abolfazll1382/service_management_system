import { describe, expect, it } from "vitest";
import { authApi, staffApi } from "@/lib/api";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { hashPassword } from "@/lib/auth/password";
import { readDb } from "@/lib/mock-server/db";
import { useMockDb } from "@/lib/store/mockDb";
import { DEMO_PASSWORD } from "@/lib/store/seed";
import {
  NATIONAL_IDS,
  rejectsWith,
  signInCustomer,
  signInStaff,
  signOutLocally,
  resetBackendBeforeEach,
  withCheckDigit,
} from "./helpers";

resetBackendBeforeEach();

const newCustomer = (overrides: Record<string, unknown> = {}) => ({
  fullName: "Nima Ahmadi",
  nationalId: withCheckDigit("123456789"),
  phone: "09151112233",
  postalCode: "1234567890",
  address: "Mashhad, Sajjad Blvd, No. 4",
  password: "Strong1pass",
  ...overrides,
});

describe("staff sign-in", () => {
  it("returns a token and a profile with no credentials in it", async () => {
    const { token, user } = await authApi.loginStaff({ username: "reza", password: DEMO_PASSWORD });
    expect(token).toMatch(/^[0-9a-f]{64}$/);
    expect(user).toMatchObject({ role: "staff", username: "reza", departmentIds: ["loan"] });
    expect(user).not.toHaveProperty("passwordHash");
    expect(user).not.toHaveProperty("passwordSalt");
  });

  it("ignores case and surrounding spaces in the username", async () => {
    await expect(authApi.loginStaff({ username: "  REZA ", password: DEMO_PASSWORD })).resolves.toBeDefined();
  });

  it("answers a wrong password and an unknown user identically", async () => {
    await rejectsWith(authApi.loginStaff({ username: "reza", password: "wrong-pass1" }), "invalid_credentials");
    await rejectsWith(authApi.loginStaff({ username: "nobody", password: DEMO_PASSWORD }), "invalid_credentials");
  });

  it("does not let a customer sign in through the staff door", async () => {
    await rejectsWith(authApi.loginStaff({ username: NATIONAL_IDS.amir, password: DEMO_PASSWORD }), "invalid_credentials");
  });
});

describe("customer sign-in", () => {
  it("signs in with national ID and password", async () => {
    const { user } = await authApi.loginCustomer({ nationalId: NATIONAL_IDS.amir, password: DEMO_PASSWORD });
    expect(user).toMatchObject({ role: "customer", nationalId: NATIONAL_IDS.amir });
    expect(user).not.toHaveProperty("passwordHash");
  });

  it("rejects a wrong password, and Persian digits (normalising them is the form's job)", async () => {
    await rejectsWith(authApi.loginCustomer({ nationalId: NATIONAL_IDS.amir, password: "nope" }), "invalid_credentials");
    await rejectsWith(authApi.loginCustomer({ nationalId: "۰۰۴۵۸۱۳۹۲۲", password: DEMO_PASSWORD }), "validation");
  });

  it("audits failed attempts without recording the full ID or the password", async () => {
    await authApi.loginCustomer({ nationalId: NATIONAL_IDS.amir, password: "bad-password1" }).catch(() => undefined);
    const failed = readDb().audit.filter((entry) => entry.action === "auth_login_failed");
    expect(failed).toHaveLength(1);
    expect(failed[0].actor).toBeNull();
    expect(failed[0].target).toBe("004•••••22");
    expect(JSON.stringify(readDb().audit)).not.toContain(NATIONAL_IDS.amir);
    expect(JSON.stringify(readDb().audit)).not.toContain("bad-password1");
  });
});

describe("registration", () => {
  it("creates a customer, signs them in, and stores only a salted hash", async () => {
    const input = newCustomer();
    const { token, user } = await authApi.register(input);
    expect(user).toMatchObject({ role: "customer", fullName: "Nima Ahmadi", nationalId: input.nationalId });
    expect(user).not.toHaveProperty("passwordHash");

    const stored = readDb().users.find((candidate) => candidate.id === user.id);
    expect(stored?.passwordHash).toMatch(/^[0-9a-f]{64}$/);
    expect(stored?.passwordHash).not.toContain("Strong1pass");
    expect(stored?.passwordHash).toBe(hashPassword("Strong1pass", stored!.passwordSalt));

    useSessionStore.getState().signIn({ token, user });
    await expect(authApi.me()).resolves.toMatchObject({ id: user.id });
    await expect(
      authApi.loginCustomer({ nationalId: input.nationalId, password: "Strong1pass" }),
    ).resolves.toBeDefined();
  });

  it("refuses a National ID or mobile number that is already registered", async () => {
    await rejectsWith(authApi.register(newCustomer({ nationalId: NATIONAL_IDS.amir })), "national_id_taken");
    await rejectsWith(authApi.register(newCustomer({ phone: "09121234567" })), "phone_taken");
  });

  it("re-validates on the server: bad checksum, bad phone, weak password", async () => {
    await rejectsWith(authApi.register(newCustomer({ nationalId: "1234567890" })), "validation");
    await rejectsWith(authApi.register(newCustomer({ phone: "9151112233" })), "validation");
    await rejectsWith(authApi.register(newCustomer({ password: "alllowercase" })), "validation");
    await rejectsWith(authApi.register(newCustomer({ fullName: "A" })), "validation");
  });

  it("cannot be used to create an admin or staff account", async () => {
    const { user } = await authApi.register(
      newCustomer({ role: "admin", departmentIds: ["loan", "vehicle"], isActive: true, username: "root" }),
    );
    expect(user.role).toBe("customer");
    expect(user).not.toHaveProperty("departmentIds");
    expect(user).not.toHaveProperty("username");
  });
});

describe("sessions", () => {
  it("rejects calls that carry no token", async () => {
    await rejectsWith(authApi.me(), "unauthenticated");
  });

  it("ends a session on logout: the old token stops working and the client is told", async () => {
    await signInStaff("reza");
    await authApi.logout();
    await rejectsWith(authApi.me(), "unauthenticated");
    expect(useSessionStore.getState()).toMatchObject({ token: null, user: null, expired: true });
  });

  it("treats an expired session as signed out", async () => {
    const { token, user } = await signInStaff("reza");
    useMockDb.setState({ sessions: { [token]: { userId: user.id, expiresAt: "2020-01-01T00:00:00.000Z" } } });
    await rejectsWith(authApi.me(), "unauthenticated");
    expect(useSessionStore.getState().expired).toBe(true);
  });

  it("does not let one client sign out another by sending a stale token", async () => {
    const first = await signInStaff("reza");
    useSessionStore.getState().signIn(await authApi.loginStaff({ username: "sara", password: DEMO_PASSWORD }));
    // The old (first) token is still valid on the server — only the client's copy changed.
    expect(readDb().sessions[first.token]).toBeDefined();
    await expect(authApi.me()).resolves.toMatchObject({ username: "sara" });
  });

  it("keeps a deactivated account's open session from working", async () => {
    const sara = await signInStaff("sara");
    signOutLocally();
    await signInStaff("admin");
    await staffApi.update(sara.user.id, { departmentIds: ["raw_material"], isActive: false });

    useSessionStore.getState().signIn(sara);
    await rejectsWith(authApi.me(), "unauthenticated");
    await rejectsWith(authApi.loginStaff({ username: "sara", password: DEMO_PASSWORD }), "invalid_credentials");
  });
});

describe("customer data stays private", () => {
  it("never sends credentials to the browser", async () => {
    await signInStaff("admin");
    const accounts = await staffApi.list();
    for (const account of accounts) {
      expect(account).not.toHaveProperty("passwordHash");
      expect(account).not.toHaveProperty("passwordSalt");
    }
    signOutLocally();
    await signInCustomer("amir");
    expect(JSON.stringify(await authApi.me())).not.toContain("passwordHash");
  });
});
