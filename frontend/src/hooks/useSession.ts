"use client";

import { useCallback } from "react";
import { authApi } from "@/lib/api";
import { can, type Action, type PolicyResource } from "@/lib/auth/policies";
import { useSessionStore } from "@/lib/auth/sessionStore";

export function useSession() {
  const user = useSessionStore((state) => state.user);
  const hydrated = useSessionStore((state) => state.hydrated);
  const expired = useSessionStore((state) => state.expired);
  return { user, hydrated, expired };
}

/**
 * `can(action, resource)` for the signed-in user. This only decides what to
 * SHOW; the server re-checks every action, so hiding a button is a courtesy,
 * not the security boundary.
 */
export function useCan() {
  const user = useSessionStore((state) => state.user);
  return useCallback((action: Action, resource?: PolicyResource) => can(user, action, resource), [user]);
}

/**
 * Ends the session and leaves for `redirectTo`.
 *
 * The server is told first (it needs the token to find the session), then the
 * browser forgets it. The way out is a full page load rather than
 * `router.push`: with a client-side push, the guard of the page being left
 * sees "signed out" in the same tick and sends the person to the sign-in
 * page instead. A fresh load also drops whatever the previous person had in
 * memory, which is what you want on a shared computer. Other open tabs notice
 * through the `storage` event and sign out too.
 */
export function useSignOut() {
  return useCallback(async (redirectTo: string) => {
    try {
      await authApi.logout();
    } catch {
      // If the server can't be reached the token is discarded locally all the same.
    }
    // Wipe the stored session but leave this page's in-memory copy alone: the page is about to be
    // replaced, and changing the store now would let its route guard react (and redirect) first.
    useSessionStore.persist.clearStorage();
    window.location.assign(redirectTo);
  }, []);
}
