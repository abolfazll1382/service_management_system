import type { Paged } from "./api";
import type { DepartmentId } from "./department";
import type { ServiceDetails } from "./service";
import type { ActorRef } from "./user";

/**
 * Deliberately ordinary administrative statuses. The allowed moves between
 * them live in lib/domain/workflow.ts so the UI and the mock server share one
 * definition.
 */
export const REQUEST_STATUSES = [
  "pending_review",
  "in_progress",
  "needs_correction",
  "approved",
  "rejected",
  "closed",
] as const;
export type RequestStatus = (typeof REQUEST_STATUSES)[number];

/** `internal` notes are staff-only; the server strips them for customers. */
export type MessageVisibility = "public" | "internal";

interface EventBase {
  id: string;
  at: string;
  actor: ActorRef;
}

export type TimelineEvent =
  | (EventBase & { kind: "submitted" })
  | (EventBase & { kind: "status_changed"; from: RequestStatus; to: RequestStatus })
  | (EventBase & { kind: "assigned"; assignee: ActorRef | null })
  | (EventBase & { kind: "message"; visibility: MessageVisibility; body: string });

/** Identity as it was when the request was filed. */
export interface CustomerSnapshot {
  fullName: string;
  nationalId: string;
  phone: string;
}

export interface ServiceRequest {
  id: string;
  /** 10-digit reference number shown to the customer. */
  trackingCode: string;
  customerId: string;
  customer: CustomerSnapshot;
  departmentId: DepartmentId;
  serviceId: string;
  description: string;
  details: ServiceDetails;
  status: RequestStatus;
  assignee: ActorRef | null;
  timeline: TimelineEvent[];
  submittedAt: string;
  updatedAt: string;
}

export type StatusCounts = Record<RequestStatus, number>;

/** Filters for the staff work queue. Everything is optional. */
export interface RequestQuery {
  status?: RequestStatus;
  departmentId?: DepartmentId;
  /** "mine" = assigned to the caller; "unassigned" = nobody has claimed it yet. */
  assignment?: "mine" | "unassigned";
  /** Matches tracking code, applicant name, national ID or phone. */
  search?: string;
  page?: number;
  pageSize?: number;
}

export interface RequestPage extends Paged<ServiceRequest> {
  /**
   * Per-status totals for the same filters EXCEPT `status` itself, so the
   * status tabs can show how many requests each one would list.
   */
  counts: StatusCounts;
}
