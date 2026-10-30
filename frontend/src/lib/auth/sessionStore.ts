import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthResult } from "@/types/api";
import type { PublicUser } from "@/types/user";
import { createBrowserStorage } from "@/lib/store/storage";

export const SESSION_STORAGE_KEY = "portal-session-v1";

interface PersistedSession {
  token: string | null;
  user: PublicUser | null;
}

interface SessionState extends PersistedSession {
  /**
   * True once the stored session has been read. Until then the server render
   * and the first client render agree on "nobody is signed in", and route
   * guards show a neutral skeleton instead of bouncing a signed-in user to
   * the login page for a frame.
   */
  hydrated: boolean;
  /** The session ended because the server stopped honouring the token. */
  expired: boolean;
  signIn: (result: AuthResult) => void;
  signOut: () => void;
  expire: () => void;
  /** Replace the cached profile (e.g. after an admin changed departments). */
  refreshUser: (user: PublicUser) => void;
}

/**
 * The browser's half of authentication: the bearer token plus a cached copy
 * of the profile for the UI. The profile is for display and for hiding
 * controls — the server decides on every call, from the token alone.
 */
export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      hydrated: false,
      expired: false,
      signIn: ({ token, user }) => set({ token, user, expired: false }),
      signOut: () => set({ token: null, user: null, expired: false }),
      expire: () => set({ token: null, user: null, expired: true }),
      refreshUser: (user) => set({ user }),
    }),
    {
      name: SESSION_STORAGE_KEY,
      version: 1,
      storage: createBrowserStorage<PersistedSession>(),
      partialize: ({ token, user }) => ({ token, user }),
      // Reading storage in the store initialiser would make the first client
      // render differ from the server's. AuthProvider calls rehydrate() in an
      // effect instead.
      skipHydration: true,
      onRehydrateStorage: () => () => {
        useSessionStore.setState({ hydrated: true });
      },
    },
  ),
);
