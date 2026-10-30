import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
import type { PublicUser, StaffProfile } from "@/types/user";

/**
 * Every permission decision in the app goes through `can()`. It is a pure
 * function over (who, what, which resource), which gives three things:
 *
 *  1. ONE place to read to understand who may do what.
 *  2. The same rules enforced twice — the mock server calls it to refuse an
 *     action, the UI calls it to hide the button. The UI check is only a
 *     convenience; the server check is the authority.
 *  3. Trivial to test exhaustively (tests/policies.test.ts walks the matrix).
 *
 * Anything not explicitly allowed is denied.
 */
export type Action =
  | "console.access"
  | "request.create"
  | "request.read"
  | "request.comment"
  | "request.comment_internal"
  | "request.transition"
  | "request.assign"
  | "staff.manage"
  | "service.manage"
  | "audit.read"
  | "demo.reset";

export interface PolicyResource {
  /** The department a request belongs to. */
  departmentId?: DepartmentId;
  /** The customer who owns a request. */
  ownerId?: string;
}

/** Actions a staff member may take on a request, scoped to their departments. */
const DEPARTMENT_SCOPED: ReadonlySet<Action> = new Set<Action>([
  "request.read",
  "request.comment",
  "request.comment_internal",
  "request.transition",
  "request.assign",
]);

function staffCan(actor: StaffProfile, action: Action, resource: PolicyResource): boolean {
  if (action === "console.access") return true;
  if (DEPARTMENT_SCOPED.has(action)) {
    return resource.departmentId !== undefined && actor.departmentIds.includes(resource.departmentId);
  }
  return false;
}

function customerCan(actor: PublicUser, action: Action, resource: PolicyResource): boolean {
  switch (action) {
    case "request.create":
      return true;
    case "request.read":
    case "request.comment":
      // Customers only ever touch their own requests, never a colleague's.
      return resource.ownerId === actor.id;
    default:
      return false;
  }
}

export function can(actor: PublicUser | null, action: Action, resource: PolicyResource = {}): boolean {
  if (!actor || !actor.isActive) return false;

  switch (actor.role) {
    case "admin":
      // Admins run the system but are not applicants, so they cannot file requests.
      return action !== "request.create";
    case "staff":
      return staffCan(actor, action, resource);
    case "customer":
      return customerCan(actor, action, resource);
  }
}

/** The departments whose requests this actor may see at all. */
export function visibleDepartments(actor: PublicUser | null): readonly DepartmentId[] {
  if (!actor || !actor.isActive) return [];
  if (actor.role === "admin") return DEPARTMENT_IDS;
  if (actor.role === "staff") return actor.departmentIds;
  return [];
}

/**
 * Who may a request be assigned to? The assignee must be an active staff
 * member of the request's department. Staff can only assign to themselves
 * (claim a request); admins can assign to anyone eligible.
 */
export function canAssignTo(
  actor: PublicUser | null,
  assignee: PublicUser | null,
  departmentId: DepartmentId,
): boolean {
  if (!can(actor, "request.assign", { departmentId })) return false;
  if (assignee === null) return true; // unassigning
  if (assignee.role !== "staff" || !assignee.isActive) return false;
  if (!assignee.departmentIds.includes(departmentId)) return false;
  return actor?.role === "admin" || actor?.id === assignee.id;
}
