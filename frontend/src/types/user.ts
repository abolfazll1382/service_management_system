import type { DepartmentId } from "./department";
import { localizedFromPlain, type Locale, type Localized } from "./i18n";

export const ROLES = ["admin", "staff", "customer"] as const;
export type Role = (typeof ROLES)[number];

interface ProfileBase {
  id: string;
  isActive: boolean;
  createdAt: string;
}

export interface CustomerProfile extends ProfileBase {
  role: "customer";
  fullName: string;
  /** کد ملی — checksum-validated at registration (see lib/utils/persianUtils). */
  nationalId: string;
  phone: string;
  postalCode: string;
  address: string;
}

export interface StaffProfile extends ProfileBase {
  role: "staff";
  username: string;
  name: Localized;
  /** The only departments this person may see or act on. */
  departmentIds: readonly DepartmentId[];
}

export interface AdminProfile extends ProfileBase {
  role: "admin";
  username: string;
  name: Localized;
}

/** Anyone who signs in to the staff console (as opposed to a customer). */
export type StaffAccount = StaffProfile | AdminProfile;

/** What the browser is allowed to hold: everything except credentials. */
export type PublicUser = CustomerProfile | StaffProfile | AdminProfile;

export interface Credentials {
  passwordHash: string;
  passwordSalt: string;
}

/** What only the (mock) server holds. Never import this type in components. */
export type StoredUser = PublicUser & Credentials;

/**
 * A lightweight, denormalised reference to "who did this", frozen at the time
 * of the action. Customers cannot read the users table (privacy), so timeline
 * events and audit rows carry their own copy of the actor's name.
 */
export interface ActorRef {
  id: string;
  role: Role;
  name: Localized;
}

export function toActorRef(user: PublicUser): ActorRef {
  return {
    id: user.id,
    role: user.role,
    name: user.role === "customer" ? localizedFromPlain(user.fullName) : user.name,
  };
}

export function displayName(user: PublicUser, locale: Locale): string {
  return user.role === "customer" ? user.fullName : user.name[locale];
}
