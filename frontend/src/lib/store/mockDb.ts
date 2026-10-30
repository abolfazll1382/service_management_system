import { create } from "zustand";
import { persist } from "zustand/middleware";
import { createBrowserStorage } from "./storage";
import { createSeedData, type MockDbData } from "./seed";

export const MOCK_DB_STORAGE_KEY = "portal-mock-db-v1";

/**
 * The mock backend's "database": plain data in a persisted Zustand store, so
 * registrations and requests survive a page refresh and can be seen from a
 * second tab (open the customer site in one, the staff console in the other).
 *
 * Only `lib/mock-server` may import this. Components and features go through
 * `lib/api`, which is the seam to replace when a real backend exists
 * (enforced by an ESLint rule). State is treated as immutable: writers
 * replace arrays and objects instead of mutating them.
 */
export const useMockDb = create<MockDbData>()(
  persist(() => createSeedData(), {
    name: MOCK_DB_STORAGE_KEY,
    version: 1,
    storage: createBrowserStorage<MockDbData>(),
    // A stored copy from a different schema version can't be trusted, and
    // this is demo data, so starting from the seed is the safe answer.
    migrate: () => createSeedData(),
  }),
);

/**
 * `localStorage` writes fire a `storage` event in every OTHER tab. Re-reading
 * on it keeps the tabs in step, so a request filed in one tab shows up in the
 * staff queue of the other the next time it fetches.
 */
if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key === MOCK_DB_STORAGE_KEY) void useMockDb.persist.rehydrate();
  });
}
