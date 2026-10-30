import { useMockDb } from "@/lib/store/mockDb";
import { createSeedData, type MockDbData } from "@/lib/store/seed";

/**
 * The only door to the mock database for the rest of lib/mock-server. Reads
 * return a plain snapshot; writes replace whole collections (never mutate in
 * place — the underlying store is immutable-by-convention).
 */
export function readDb(): MockDbData {
  const { users, requests, serviceActive, sessions, audit } = useMockDb.getState();
  return { users, requests, serviceActive, sessions, audit };
}

export function writeDb(patch: Partial<MockDbData>): void {
  useMockDb.setState(patch);
}

export function resetDb(data: MockDbData = createSeedData()): void {
  useMockDb.setState(data);
}

export function nowIso(): string {
  return new Date().toISOString();
}
