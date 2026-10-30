import type { ServiceRequest } from "@/types/request";
import type { PublicUser, StaffAccount, StoredUser } from "@/types/user";
import { can } from "@/lib/auth/policies";

/** Strips credentials. Nothing returned across the API boundary may carry them. */
export function toPublicUser(user: StoredUser): PublicUser {
  const { passwordHash: _hash, passwordSalt: _salt, ...profile } = user;
  return profile;
}

export function toStaffAccount(user: StoredUser): StaffAccount {
  const profile = toPublicUser(user);
  if (profile.role === "customer") throw new Error("A customer is not a staff account");
  return profile;
}

/**
 * What THIS viewer is allowed to see of a request. Internal staff notes are
 * removed on the "server" for anyone who couldn't have written them, so a
 * customer's browser never receives them — hiding them in the UI alone would
 * leave them readable in the network tab.
 */
export function viewRequestFor(viewer: PublicUser, request: ServiceRequest): ServiceRequest {
  if (can(viewer, "request.comment_internal", { departmentId: request.departmentId })) return request;
  return {
    ...request,
    timeline: request.timeline.filter((event) => !(event.kind === "message" && event.visibility === "internal")),
  };
}
