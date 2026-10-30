import { ApiError } from "@/types/api";
import { useSessionStore } from "@/lib/auth/sessionStore";
import type { ServerContext } from "@/lib/mock-server/session";

/**
 * The seam between the UI and the mock server — what `fetch` plus an auth
 * header would be against a real backend. It does the things a network does:
 * takes time, occasionally fails, and carries the bearer token. Swapping in a
 * real backend means rewriting the modules in lib/api to call `fetch`; the
 * hooks and components above them don't change.
 */
interface MockClientConfig {
  /** Multiplies every simulated delay. 0 answers on the next tick (tests). */
  latencyScale: number;
  /** Chance (0–1) that a call fails with `network` before reaching the server. */
  failureRate: number;
}

function parseRate(raw: string | undefined): number {
  const value = Number(raw);
  return Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0;
}

let config: MockClientConfig = {
  latencyScale: 1,
  // e.g. NEXT_PUBLIC_MOCK_FAILURE_RATE=0.3 to see every retry/error state in the UI.
  failureRate: parseRate(process.env.NEXT_PUBLIC_MOCK_FAILURE_RATE),
};

export function configureMockClient(next: Partial<MockClientConfig>): void {
  config = { ...config, ...next };
}

export function mockRequest<T>(handler: (ctx: ServerContext) => T): Promise<T> {
  // The token is attached when the call is MADE, like a header on an outgoing
  // request — signing out while it is in flight doesn't change who it was for.
  const ctx: ServerContext = { token: useSessionStore.getState().token };
  const delay = (150 + Math.random() * 250) * config.latencyScale;

  return new Promise<T>((resolve, reject) => {
    setTimeout(() => {
      if (Math.random() < config.failureRate) {
        reject(new ApiError("network"));
        return;
      }
      try {
        resolve(handler(ctx));
      } catch (error) {
        if (error instanceof ApiError) {
          // The server no longer honours our token (expired, account switched
          // off, demo reset). End the session so route guards send us to sign-in.
          const session = useSessionStore.getState();
          if (error.code === "unauthenticated" && ctx.token !== null && session.token === ctx.token) session.expire();
          reject(error);
          return;
        }
        // A bug, not a business error: surface it in the console, show the generic message.
        console.error("[mock-server] unexpected error", error);
        reject(new ApiError("network"));
      }
    }, delay);
  });
}
