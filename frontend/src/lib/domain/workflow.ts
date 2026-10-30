import type { RequestStatus } from "@/types/request";

/**
 * The status state machine. Defining the legal moves as data means the work
 * panel only offers valid next steps AND the mock server rejects anything
 * else — a client that skips the UI still can't jump from "pending review"
 * straight to "approved".
 */
export const ALLOWED_TRANSITIONS: Readonly<Record<RequestStatus, readonly RequestStatus[]>> = {
  pending_review: ["in_progress", "rejected"],
  in_progress: ["needs_correction", "approved", "rejected"],
  needs_correction: ["in_progress", "rejected"],
  approved: ["closed"],
  rejected: ["closed"],
  closed: [],
};

export function nextStatuses(from: RequestStatus): readonly RequestStatus[] {
  return ALLOWED_TRANSITIONS[from];
}

export function canTransition(from: RequestStatus, to: RequestStatus): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}

export function isClosed(status: RequestStatus): boolean {
  return status === "closed";
}

/** Still needs someone's attention. */
export function isOpen(status: RequestStatus): boolean {
  return status === "pending_review" || status === "in_progress" || status === "needs_correction";
}

/**
 * Decisions the applicant has to be able to act on come with a reason:
 * a rejection that says nothing, or a correction request that doesn't say
 * what to correct, is useless. Enforced by the mock server and the work panel.
 */
const NOTE_REQUIRED: ReadonlySet<RequestStatus> = new Set<RequestStatus>(["rejected", "needs_correction"]);

export function requiresNote(to: RequestStatus): boolean {
  return NOTE_REQUIRED.has(to);
}
