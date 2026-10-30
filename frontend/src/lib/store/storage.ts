import { createJSONStorage, type StateStorage } from "zustand/middleware";

const memory = new Map<string, string>();

/** Used during SSR and in tests, where there is no `window.localStorage`. */
const memoryStorage: StateStorage = {
  getItem: (key) => memory.get(key) ?? null,
  setItem: (key, value) => {
    memory.set(key, value);
  },
  removeItem: (key) => {
    memory.delete(key);
  },
};

/**
 * Touching `localStorage` on the server throws (and on newer Node versions
 * the global exists but misbehaves without a flag), so the browser check is
 * explicit rather than relying on a try/catch around the global.
 */
export function createBrowserStorage<State>() {
  return createJSONStorage<State>(() => (typeof window === "undefined" ? memoryStorage : window.localStorage));
}
