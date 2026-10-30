import { z } from "zod";
import { ApiError } from "@/types/api";
import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
import {
  REQUEST_STATUSES,
  type RequestPage,
  type ServiceRequest,
  type StatusCounts,
  type TimelineEvent,
} from "@/types/request";
import { toActorRef, type ActorRef, type StoredUser } from "@/types/user";
import { can, canAssignTo, visibleDepartments, type Action } from "@/lib/auth/policies";
import { findService } from "@/lib/catalog";
import { canTransition, isClosed } from "@/lib/domain/workflow";
import { createId } from "@/lib/utils/id";
import { generateTrackingCode, normalizeDigits } from "@/lib/utils/persianUtils";
import { identityTranslate } from "@/lib/validation/fields";
import {
  createDetailsSchema,
  createMessageSchema,
  createTransitionSchema,
  descriptionField,
  statusSchema,
  toServiceDetails,
} from "@/lib/validation/request";
import { appendAudit } from "./audit";
import { isServiceActive } from "./catalog";
import { nowIso, readDb, writeDb } from "./db";
import { authorize, requireActor, type ServerContext } from "./session";
import { parseInput } from "./validate";
import { viewRequestFor } from "./views";

/* ------------------------------------------------------------------ */
/* Shared helpers                                                      */
/* ------------------------------------------------------------------ */

/**
 * Finds a request AND checks the caller may perform `action` on it.
 *
 * Two different refusals on purpose: someone who may not even READ the
 * request gets `not_found` if they are a customer (ids and tracking codes
 * must not be probeable) and `forbidden` if they are staff (an explicit
 * "that belongs to another department" is the useful answer for an insider).
 * Someone who can read it but not do this particular thing gets `forbidden`.
 */
function loadAuthorized(actor: StoredUser, requestId: string, action: Action): ServiceRequest {
  const request = readDb().requests.find((candidate) => candidate.id === requestId);
  if (!request) throw new ApiError("not_found");

  const resource = { departmentId: request.departmentId, ownerId: request.customerId };
  if (!can(actor, "request.read", resource)) throw new ApiError(actor.role === "customer" ? "not_found" : "forbidden");
  if (!can(actor, action, resource)) throw new ApiError("forbidden");
  return request;
}

function replaceRequest(updated: ServiceRequest): ServiceRequest[] {
  return readDb().requests.map((request) => (request.id === updated.id ? updated : request));
}

function withEvents(
  request: ServiceRequest,
  events: TimelineEvent[],
  at: string,
  changes: Partial<Pick<ServiceRequest, "status" | "assignee">> = {},
): ServiceRequest {
  return { ...request, ...changes, timeline: [...request.timeline, ...events], updatedAt: at };
}

function uniqueTrackingCode(requests: readonly ServiceRequest[]): string {
  // 10^10 possibilities: a collision is vanishingly rare, but the contract is "unique".
  for (let attempt = 0; attempt < 25; attempt++) {
    const code = generateTrackingCode();
    if (!requests.some((request) => request.trackingCode === code)) return code;
  }
  throw new Error("Could not allocate a unique tracking code");
}

/* ------------------------------------------------------------------ */
/* Customer side                                                       */
/* ------------------------------------------------------------------ */

const createRequestSchema = z.object({
  serviceId: z.string().min(1),
  description: descriptionField(identityTranslate),
  details: z.record(z.string(), z.unknown()),
});

export function createRequest(ctx: ServerContext, input: unknown): ServiceRequest {
  const actor = requireActor(ctx);
  authorize(actor, "request.create");
  if (actor.role !== "customer") throw new ApiError("forbidden");

  const base = parseInput(createRequestSchema, input);
  const service = findService(base.serviceId);
  if (!service) throw new ApiError("not_found");
  if (!isServiceActive(service.id)) throw new ApiError("service_unavailable");
  const details = toServiceDetails(service.fields, parseInput(createDetailsSchema(service.fields, identityTranslate), base.details));

  const db = readDb();
  const id = `req-${createId()}`;
  const at = nowIso();
  const request: ServiceRequest = {
    id,
    trackingCode: uniqueTrackingCode(db.requests),
    customerId: actor.id,
    // A snapshot: the request keeps showing who filed it even if the profile changes later.
    customer: { fullName: actor.fullName, nationalId: actor.nationalId, phone: actor.phone },
    departmentId: service.departmentId,
    serviceId: service.id,
    description: base.description,
    details,
    status: "pending_review",
    assignee: null,
    timeline: [{ id: `${id}-e0`, kind: "submitted", at, actor: toActorRef(actor) }],
    submittedAt: at,
    updatedAt: at,
  };

  writeDb({
    requests: [...db.requests, request],
    audit: appendAudit(db.audit, { actor: toActorRef(actor), action: "request_created", target: request.trackingCode }),
  });
  return viewRequestFor(actor, request);
}

export function listMyRequests(ctx: ServerContext): ServiceRequest[] {
  const actor = requireActor(ctx);
  if (actor.role !== "customer") throw new ApiError("forbidden");
  return readDb()
    .requests.filter((request) => request.customerId === actor.id)
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .map((request) => viewRequestFor(actor, request));
}

/** One request, for whoever may read it: its owner, its department's staff, or an admin. */
export function getRequest(ctx: ServerContext, requestId: string): ServiceRequest {
  const actor = requireActor(ctx);
  return viewRequestFor(actor, loadAuthorized(actor, requestId, "request.read"));
}

/* ------------------------------------------------------------------ */
/* Staff side                                                          */
/* ------------------------------------------------------------------ */

const queueQuerySchema = z.object({
  status: statusSchema.optional(),
  departmentId: z.enum(DEPARTMENT_IDS).optional(),
  assignment: z.enum(["mine", "unassigned"]).optional(),
  search: z.string().max(100).optional(),
  page: z.number().int().min(1).optional(),
  pageSize: z.number().int().min(1).max(50).optional(),
});

function countByStatus(requests: readonly ServiceRequest[]): StatusCounts {
  const counts = Object.fromEntries(REQUEST_STATUSES.map((status) => [status, 0])) as StatusCounts;
  for (const request of requests) counts[request.status] += 1;
  return counts;
}

function matchesSearch(request: ServiceRequest, needle: string): boolean {
  return (
    request.trackingCode.includes(needle) ||
    request.customer.nationalId.includes(needle) ||
    request.customer.phone.includes(needle) ||
    request.customer.fullName.toLowerCase().includes(needle)
  );
}

/**
 * The work queue. The department scope is applied FIRST, from the caller's
 * grants, so no filter a client sends can widen it: Sara's queue simply
 * never contains a vehicle request, and asking for one by `departmentId` is
 * refused outright.
 */
export function queueRequests(ctx: ServerContext, query: unknown): RequestPage {
  const actor = requireActor(ctx);
  authorize(actor, "console.access");
  const { status, departmentId, assignment, search, page = 1, pageSize = 10 } = parseInput(queueQuerySchema, query ?? {});

  const visible = visibleDepartments(actor);
  if (departmentId !== undefined && !visible.includes(departmentId)) throw new ApiError("forbidden");
  const scope: readonly DepartmentId[] = departmentId ? [departmentId] : visible;

  let items = readDb().requests.filter((request) => scope.includes(request.departmentId));
  if (assignment === "mine") items = items.filter((request) => request.assignee?.id === actor.id);
  if (assignment === "unassigned") items = items.filter((request) => request.assignee === null);
  const needle = search ? normalizeDigits(search.trim().toLowerCase()) : "";
  if (needle) items = items.filter((request) => matchesSearch(request, needle));

  const counts = countByStatus(items);
  if (status) items = items.filter((request) => request.status === status);
  items = [...items].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));

  const start = (page - 1) * pageSize;
  return {
    items: items.slice(start, start + pageSize).map((request) => viewRequestFor(actor, request)),
    total: items.length,
    page,
    pageSize,
    counts,
  };
}

export function transitionRequest(ctx: ServerContext, requestId: string, input: unknown): ServiceRequest {
  const actor = requireActor(ctx);
  const { to, note: rawNote } = parseInput(createTransitionSchema(identityTranslate), input);
  const note = rawNote === "" ? undefined : rawNote;
  const request = loadAuthorized(actor, requestId, "request.transition");

  if (isClosed(request.status)) throw new ApiError("request_closed");
  if (!canTransition(request.status, to)) throw new ApiError("invalid_transition");

  const at = nowIso();
  const by = toActorRef(actor);
  const events: TimelineEvent[] = [];
  let assignee = request.assignee;

  // Starting a review claims the request, so two colleagues don't both pick it up.
  if (actor.role === "staff" && request.status === "pending_review" && to === "in_progress" && assignee === null) {
    assignee = by;
    events.push({ id: createId(), kind: "assigned", at, actor: by, assignee: by });
  }
  events.push({ id: createId(), kind: "status_changed", at, actor: by, from: request.status, to });
  if (note) events.push({ id: createId(), kind: "message", at, actor: by, visibility: "public", body: note });

  const updated = withEvents(request, events, at, { status: to, assignee });
  const db = readDb();
  writeDb({
    requests: replaceRequest(updated),
    audit: appendAudit(db.audit, { actor: by, action: "request_status_changed", target: request.trackingCode }),
  });
  return viewRequestFor(actor, updated);
}

const assignSchema = z.object({ assigneeId: z.string().min(1).nullable() });

export function assignRequest(ctx: ServerContext, requestId: string, input: unknown): ServiceRequest {
  const actor = requireActor(ctx);
  const { assigneeId } = parseInput(assignSchema, input);
  const request = loadAuthorized(actor, requestId, "request.assign");
  if (isClosed(request.status)) throw new ApiError("request_closed");

  const db = readDb();
  const assignee = assigneeId === null ? null : (db.users.find((user) => user.id === assigneeId) ?? null);
  if (assigneeId !== null && assignee === null) throw new ApiError("not_found");
  if (!canAssignTo(actor, assignee, request.departmentId)) throw new ApiError("forbidden");

  const assigneeRef: ActorRef | null = assignee ? toActorRef(assignee) : null;
  if (assigneeRef?.id === request.assignee?.id) return viewRequestFor(actor, request); // nothing to change

  const at = nowIso();
  const by = toActorRef(actor);
  const updated = withEvents(request, [{ id: createId(), kind: "assigned", at, actor: by, assignee: assigneeRef }], at, {
    assignee: assigneeRef,
  });
  writeDb({
    requests: replaceRequest(updated),
    audit: appendAudit(db.audit, { actor: by, action: "request_assigned", target: request.trackingCode }),
  });
  return viewRequestFor(actor, updated);
}

/** Who the caller could assign this department's requests to (themselves, or anyone eligible for an admin). */
export function assignableStaff(ctx: ServerContext, departmentIdInput: unknown): ActorRef[] {
  const actor = requireActor(ctx);
  const departmentId = parseInput(z.enum(DEPARTMENT_IDS), departmentIdInput);
  authorize(actor, "request.assign", { departmentId });
  return readDb()
    .users.filter((user) => canAssignTo(actor, user, departmentId))
    .map(toActorRef);
}

/* ------------------------------------------------------------------ */
/* Both sides                                                          */
/* ------------------------------------------------------------------ */

export function addMessage(ctx: ServerContext, requestId: string, input: unknown): ServiceRequest {
  const actor = requireActor(ctx);
  const { body, visibility } = parseInput(createMessageSchema(identityTranslate), input);
  const request = loadAuthorized(actor, requestId, visibility === "internal" ? "request.comment_internal" : "request.comment");
  if (isClosed(request.status)) throw new ApiError("request_closed");

  const at = nowIso();
  const by = toActorRef(actor);
  const events: TimelineEvent[] = [{ id: createId(), kind: "message", at, actor: by, visibility, body }];
  let status = request.status;

  // An applicant answering a correction request hands the ball back to staff.
  // They still can't change a status themselves; the server does it as the
  // consequence of an action they ARE allowed to take.
  if (actor.role === "customer" && request.status === "needs_correction") {
    status = "in_progress";
    events.push({ id: createId(), kind: "status_changed", at, actor: by, from: "needs_correction", to: status });
  }

  const updated = withEvents(request, events, at, { status });
  const db = readDb();
  writeDb({
    requests: replaceRequest(updated),
    audit: appendAudit(db.audit, { actor: by, action: "request_message_added", target: request.trackingCode }),
  });
  return viewRequestFor(actor, updated);
}
