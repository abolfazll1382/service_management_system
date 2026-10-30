import { beforeEach, expect } from "vitest";
import { authApi, configureMockClient } from "@/lib/api";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { resetDb } from "@/lib/mock-server/db";
import { DEMO_PASSWORD } from "@/lib/store/seed";
import type { ApiErrorCode } from "@/types/api";

export const NATIONAL_IDS = { amir: "0045813922", maryam: "1277348561", hossein: "0592846717" } as const;

/** Seeded requests, by department. See lib/store/seed.ts. */
export const REQ = {
  loanInProgress: "req-seed-1", // amir, assigned to reza
  vehiclePending: "req-seed-2", // amir
  rawNeedsCorrection: "req-seed-3", // maryam, assigned to sara
  housingApproved: "req-seed-4", // maryam, has an INTERNAL note
  loanPending: "req-seed-5", // hossein, unassigned
  rawClosed: "req-seed-6", // hossein
  housingInProgress: "req-seed-7", // amir
  vehicleRejected: "req-seed-8", // hossein
} as const;

export { withCheckDigit } from "./nationalId";

/** Fresh seeded database, nobody signed in, instant responses, no random failures. */
export function resetBackendBeforeEach(): void {
  beforeEach(() => {
    configureMockClient({ latencyScale: 0, failureRate: 0 });
    resetDb();
    useSessionStore.getState().signOut();
  });
}

export async function signInStaff(username: string) {
  const result = await authApi.loginStaff({ username, password: DEMO_PASSWORD });
  useSessionStore.getState().signIn(result);
  return result;
}

export async function signInCustomer(who: keyof typeof NATIONAL_IDS) {
  const result = await authApi.loginCustomer({ nationalId: NATIONAL_IDS[who], password: DEMO_PASSWORD });
  useSessionStore.getState().signIn(result);
  return result;
}

export function signOutLocally(): void {
  useSessionStore.getState().signOut();
}

export async function rejectsWith(promise: Promise<unknown>, code: ApiErrorCode): Promise<void> {
  await expect(promise).rejects.toMatchObject({ name: "ApiError", code });
}

export const validLoan = {
  serviceId: "personal-loan",
  description: "I need a loan to pay for wedding costs.",
  details: { amount: 100_000_000, termMonths: "12", purpose: "Wedding" },
};
