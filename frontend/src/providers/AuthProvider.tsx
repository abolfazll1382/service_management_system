"use client";

import { useEffect, type ReactNode } from "react";
import { authApi } from "@/lib/api";
import { SESSION_STORAGE_KEY, useSessionStore } from "@/lib/auth/sessionStore";

/**
 * Brings the persisted session into the app AFTER hydration, keeps tabs in
 * step, and double-checks the stored session with the server.
 *
 * - Reading storage in an effect (not during render) is what keeps the first
 *   client render identical to the server's, so there is no hydration mismatch.
 * - A `storage` event means ANOTHER tab signed in or out; follow it.
 * - The cached profile can be stale (an admin may have changed this person's
 *   departments) or the token dead (demo reset). `me()` refreshes the former;
 *   for the latter the API client expires the session and the guards react.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const hydrated = useSessionStore((state) => state.hydrated);
  const token = useSessionStore((state) => state.token);

  useEffect(() => {
    void useSessionStore.persist.rehydrate();
    const onStorage = (event: StorageEvent) => {
      if (event.key === SESSION_STORAGE_KEY) void useSessionStore.persist.rehydrate();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    if (!hydrated || token === null) return;
    let cancelled = false;
    authApi
      .me()
      .then((user) => {
        if (!cancelled) useSessionStore.getState().refreshUser(user);
      })
      .catch(() => undefined); // an `unauthenticated` answer already ended the session
    return () => {
      cancelled = true;
    };
  }, [hydrated, token]);

  return children;
}
