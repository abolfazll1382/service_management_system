import { ApiError } from "@/types/api";
import type { TimelineEvent } from "@/types/request";
import { toActorRef, type StaffAccount, type StaffProfile, type StoredUser } from "@/types/user";
import { generateSalt, hashPassword } from "@/lib/auth/password";
import { isOpen } from "@/lib/domain/workflow";
import { createId } from "@/lib/utils/id";
import { identityTranslate } from "@/lib/validation/fields";
import { createStaffInputSchema, updateStaffInputSchema } from "@/lib/validation/staff";
import { appendAudit } from "./audit";
import { nowIso, readDb, writeDb } from "./db";
import { authorize, closeSessionsOf, requireActor, type ServerContext } from "./session";
import { parseInput } from "./validate";
import { toStaffAccount } from "./views";

export function listStaff(ctx: ServerContext): StaffAccount[] {
  const actor = requireActor(ctx);
  authorize(actor, "staff.manage");
  return readDb()
    .users.filter((user) => user.role !== "customer")
    .map(toStaffAccount)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt));
}

export function createStaff(ctx: ServerContext, input: unknown): StaffProfile {
  const actor = requireActor(ctx);
  authorize(actor, "staff.manage");
  const data = parseInput(createStaffInputSchema(identityTranslate), input);

  const db = readDb();
  const taken = db.users.some((user) => user.role !== "customer" && user.username.toLowerCase() === data.username);
  if (taken) throw new ApiError("username_taken");

  const passwordSalt = generateSalt();
  const user: StoredUser & StaffProfile = {
    id: `u-${createId()}`,
    role: "staff",
    username: data.username,
    name: { fa: data.nameFa, en: data.nameEn },
    departmentIds: [...new Set(data.departmentIds)],
    isActive: true,
    createdAt: nowIso(),
    passwordSalt,
    passwordHash: hashPassword(data.password, passwordSalt),
  };
  writeDb({
    users: [...db.users, user],
    audit: appendAudit(db.audit, { actor: toActorRef(actor), action: "staff_created", target: user.username }),
  });
  return toStaffProfile(user);
}

/**
 * Changes a staff member's departments or switches the account on/off.
 * Admin accounts can't be edited here, so nobody can lock the last
 * administrator out of the system through the UI.
 */
export function updateStaff(ctx: ServerContext, staffId: string, input: unknown): StaffProfile {
  const actor = requireActor(ctx);
  authorize(actor, "staff.manage");
  const data = parseInput(updateStaffInputSchema(identityTranslate), input);

  const db = readDb();
  const target = db.users.find((user) => user.id === staffId);
  if (!target) throw new ApiError("not_found");
  if (target.role !== "staff") throw new ApiError("forbidden");

  const updatedUser: StoredUser & StaffProfile = {
    ...target,
    departmentIds: [...new Set(data.departmentIds)],
    isActive: data.isActive,
  };

  // Don't leave open work assigned to someone who can no longer touch it.
  const at = nowIso();
  const by = toActorRef(actor);
  const requests = db.requests.map((request) => {
    const stranded =
      request.assignee?.id === target.id &&
      isOpen(request.status) &&
      (!updatedUser.isActive || !updatedUser.departmentIds.includes(request.departmentId));
    if (!stranded) return request;
    const event: TimelineEvent = { id: createId(), kind: "assigned", at, actor: by, assignee: null };
    return { ...request, assignee: null, timeline: [...request.timeline, event], updatedAt: at };
  });

  writeDb({
    users: db.users.map((user) => (user.id === target.id ? updatedUser : user)),
    requests,
    audit: appendAudit(db.audit, { actor: by, action: "staff_updated", target: target.username }),
  });
  // Deactivation takes effect immediately, not at the person's next login.
  if (!updatedUser.isActive) closeSessionsOf(target.id);
  return toStaffProfile(updatedUser);
}

function toStaffProfile(user: StoredUser): StaffProfile {
  const account = toStaffAccount(user);
  if (account.role !== "staff") throw new Error("Expected a staff profile");
  return account;
}
