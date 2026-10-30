import type { ActorRef } from "./user";

/** snake_case (no dots) so each action doubles as a dictionary key segment. */
export const AUDIT_ACTIONS = [
  "auth_register",
  "auth_login",
  "auth_login_failed",
  "request_created",
  "request_status_changed",
  "request_assigned",
  "request_message_added",
  "staff_created",
  "staff_updated",
  "service_paused",
  "service_resumed",
  "demo_reset",
] as const;
export type AuditAction = (typeof AUDIT_ACTIONS)[number];

export interface AuditEntry {
  id: string;
  at: string;
  /** null for events with no authenticated actor (e.g. a failed login). */
  actor: ActorRef | null;
  action: AuditAction;
  /** A language-neutral identifier: tracking code, username or service id. */
  target?: string;
}
