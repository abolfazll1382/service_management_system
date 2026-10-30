import { ApiError, type AuthResult } from "@/types/api";
import { toActorRef, type StoredUser } from "@/types/user";
import { generateSalt, hashPassword, verifyPassword } from "@/lib/auth/password";
import {
  createCustomerLoginSchema,
  createRegisterInputSchema,
  createStaffLoginSchema,
} from "@/lib/validation/auth";
import { identityTranslate } from "@/lib/validation/fields";
import { createId } from "@/lib/utils/id";
import { maskNationalId } from "@/lib/utils/mask";
import { appendAudit } from "./audit";
import { nowIso, readDb, writeDb } from "./db";
import { closeSession, openSession, requireActor, type ServerContext } from "./session";
import { parseInput } from "./validate";
import { toPublicUser } from "./views";

/**
 * Compared against when the account doesn't exist, so "no such user" and
 * "wrong password" do the same work and give the same answer — the response
 * never reveals which of the two it was.
 */
const DECOY = { passwordSalt: "decoy", passwordHash: "0".repeat(64) };

function failedLogin(target: string): never {
  const db = readDb();
  writeDb({ audit: appendAudit(db.audit, { actor: null, action: "auth_login_failed", target }) });
  throw new ApiError("invalid_credentials");
}

function succeed(user: StoredUser, action: "auth_register" | "auth_login"): AuthResult {
  const db = readDb();
  writeDb({ audit: appendAudit(db.audit, { actor: toActorRef(user), action }) });
  return { token: openSession(user.id), user: toPublicUser(user) };
}

export function register(input: unknown): AuthResult {
  const data = parseInput(createRegisterInputSchema(identityTranslate), input);
  const db = readDb();

  const customers = db.users.filter((user) => user.role === "customer");
  if (customers.some((user) => user.nationalId === data.nationalId)) throw new ApiError("national_id_taken");
  if (customers.some((user) => user.phone === data.phone)) throw new ApiError("phone_taken");

  const passwordSalt = generateSalt();
  const user: StoredUser = {
    id: `c-${createId()}`,
    role: "customer",
    fullName: data.fullName,
    nationalId: data.nationalId,
    phone: data.phone,
    postalCode: data.postalCode,
    address: data.address,
    isActive: true,
    createdAt: nowIso(),
    passwordSalt,
    passwordHash: hashPassword(data.password, passwordSalt),
  };
  writeDb({ users: [...db.users, user] });
  return succeed(user, "auth_register");
}

export function loginCustomer(input: unknown): AuthResult {
  const { nationalId, password } = parseInput(createCustomerLoginSchema(identityTranslate), input);
  const user = readDb().users.find((candidate) => candidate.role === "customer" && candidate.nationalId === nationalId);

  const credentials = user ?? DECOY;
  const passwordOk = verifyPassword(password, credentials.passwordSalt, credentials.passwordHash);
  if (!user || !user.isActive || !passwordOk) failedLogin(maskNationalId(nationalId));
  return succeed(user, "auth_login");
}

/** Staff and administrators share this entry point; customers have no username. */
export function loginStaff(input: unknown): AuthResult {
  const { username, password } = parseInput(createStaffLoginSchema(identityTranslate), input);
  const wanted = username.toLowerCase();
  const user = readDb().users.find(
    (candidate) => candidate.role !== "customer" && candidate.username.toLowerCase() === wanted,
  );

  const credentials = user ?? DECOY;
  const passwordOk = verifyPassword(password, credentials.passwordSalt, credentials.passwordHash);
  if (!user || !user.isActive || !passwordOk) failedLogin(wanted);
  return succeed(user, "auth_login");
}

export function logout(ctx: ServerContext): void {
  closeSession(ctx.token);
}

/** Who does this token belong to? Lets the browser notice a dead or stale session. */
export function currentUser(ctx: ServerContext) {
  return toPublicUser(requireActor(ctx));
}
