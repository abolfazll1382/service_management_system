import { ApiError } from "@/types/api";
import type { PublicUser, StoredUser } from "@/types/user";
import { can, type Action, type PolicyResource } from "@/lib/auth/policies";
import { createToken } from "@/lib/utils/id";
import { readDb, writeDb } from "./db";

/**
 * What the transport hands the server alongside the call: the bearer token,
 * exactly as an `Authorization` header would. The server derives identity
 * from it and from nothing else — no handler accepts a "who am I" argument.
 */
export interface ServerContext {
  token: string | null;
}

const SESSION_TTL_MS = 8 * 60 * 60 * 1000;

export function openSession(userId: string): string {
  const db = readDb();
  const now = Date.now();
  // Drop expired sessions while we're here so the table can't grow forever.
  const live = Object.fromEntries(
    Object.entries(db.sessions).filter(([, session]) => Date.parse(session.expiresAt) > now),
  );
  const token = createToken();
  writeDb({ sessions: { ...live, [token]: { userId, expiresAt: new Date(now + SESSION_TTL_MS).toISOString() } } });
  return token;
}

export function closeSession(token: string | null): void {
  if (token === null) return;
  const { sessions } = readDb();
  if (!(token in sessions)) return;
  const { [token]: _closed, ...rest } = sessions;
  writeDb({ sessions: rest });
}

/** Signs a user out everywhere — used when an account is deactivated. */
export function closeSessionsOf(userId: string): void {
  const { sessions } = readDb();
  writeDb({ sessions: Object.fromEntries(Object.entries(sessions).filter(([, s]) => s.userId !== userId)) });
}

export function resolveActor(ctx: ServerContext): StoredUser | null {
  if (ctx.token === null) return null;
  const db = readDb();
  const session = db.sessions[ctx.token];
  if (!session || Date.parse(session.expiresAt) <= Date.now()) return null;
  const user = db.users.find((candidate) => candidate.id === session.userId);
  // A deactivated account is treated like no session at all.
  return user && user.isActive ? user : null;
}

export function requireActor(ctx: ServerContext): StoredUser {
  const actor = resolveActor(ctx);
  if (!actor) throw new ApiError("unauthenticated");
  return actor;
}

/** Throws `forbidden` unless the shared policy allows it. */
export function authorize(actor: PublicUser | null, action: Action, resource: PolicyResource = {}): void {
  if (!can(actor, action, resource)) throw new ApiError("forbidden");
}
