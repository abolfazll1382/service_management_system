import { describe, expect, it } from "vitest";
import { can, canAssignTo, visibleDepartments, type Action } from "@/lib/auth/policies";
import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
import type { PublicUser, StaffProfile } from "@/types/user";

const base = { isActive: true, createdAt: "2026-01-01T00:00:00.000Z" };
const name = { fa: "نام", en: "Name" };

const admin: PublicUser = { ...base, id: "a1", role: "admin", username: "admin", name };
const staff = (id: string, departmentIds: DepartmentId[], isActive = true): StaffProfile => ({
  ...base,
  isActive,
  id,
  role: "staff",
  username: id,
  name,
  departmentIds,
});
const customer = (id: string, isActive = true): PublicUser => ({
  ...base,
  isActive,
  id,
  role: "customer",
  fullName: "Customer",
  nationalId: "0045813922",
  phone: "09121234567",
  postalCode: "1458943671",
  address: "Somewhere 12",
});

const reza = staff("reza", ["loan"]);
const sara = staff("sara", ["raw_material"]);
const multi = staff("multi", ["loan", "housing"]);

const ALL_ACTIONS: Action[] = [
  "console.access",
  "request.create",
  "request.read",
  "request.comment",
  "request.comment_internal",
  "request.transition",
  "request.assign",
  "staff.manage",
  "service.manage",
  "audit.read",
  "demo.reset",
];
const DEPARTMENT_SCOPED: Action[] = [
  "request.read",
  "request.comment",
  "request.comment_internal",
  "request.transition",
  "request.assign",
];

describe("can(): default deny", () => {
  it("denies everything when nobody is signed in", () => {
    for (const action of ALL_ACTIONS) expect(can(null, action, { departmentId: "loan", ownerId: "x" })).toBe(false);
  });

  it("denies everything to a deactivated account, whatever its role", () => {
    const inactive = [staff("gone", ["loan"], false), customer("gone-c", false), { ...admin, isActive: false }];
    for (const actor of inactive) {
      for (const action of ALL_ACTIONS) {
        expect(can(actor, action, { departmentId: "loan", ownerId: actor.id }), `${actor.role}:${action}`).toBe(false);
      }
    }
  });
});

describe("can(): staff are confined to their departments", () => {
  it.each(DEPARTMENT_SCOPED)("%s is allowed only inside a granted department", (action) => {
    for (const actor of [reza, sara, multi]) {
      for (const departmentId of DEPARTMENT_IDS) {
        expect(can(actor, action, { departmentId }), `${actor.id} ${action} ${departmentId}`).toBe(
          actor.departmentIds.includes(departmentId),
        );
      }
    }
  });

  it("denies a department-scoped action when no department is given", () => {
    for (const action of DEPARTMENT_SCOPED) expect(can(reza, action, {})).toBe(false);
  });

  it("lets staff into the console but never into administration", () => {
    expect(can(reza, "console.access")).toBe(true);
    for (const action of ["staff.manage", "service.manage", "audit.read", "demo.reset", "request.create"] as const) {
      expect(can(reza, action, { departmentId: "loan" }), action).toBe(false);
    }
  });

  it("gives a multi-department staff member exactly the union of their grants", () => {
    expect(visibleDepartments(multi)).toEqual(["loan", "housing"]);
    expect(can(multi, "request.read", { departmentId: "housing" })).toBe(true);
    expect(can(multi, "request.read", { departmentId: "vehicle" })).toBe(false);
  });
});

describe("can(): customers only touch their own requests", () => {
  const amir = customer("amir");

  it("may create requests", () => expect(can(amir, "request.create")).toBe(true));

  it("may read and comment on their own request only", () => {
    for (const action of ["request.read", "request.comment"] as const) {
      expect(can(amir, action, { departmentId: "loan", ownerId: "amir" })).toBe(true);
      expect(can(amir, action, { departmentId: "loan", ownerId: "someone-else" })).toBe(false);
      expect(can(amir, action, { departmentId: "loan" })).toBe(false);
    }
  });

  it("can never act as staff, even on their own request", () => {
    const own = { departmentId: "loan" as const, ownerId: "amir" };
    for (const action of ["console.access", "request.comment_internal", "request.transition", "request.assign", "staff.manage", "service.manage", "audit.read", "demo.reset"] as const) {
      expect(can(amir, action, own), action).toBe(false);
    }
  });
});

describe("can(): administrators", () => {
  it("may do everything except file a request as an applicant", () => {
    for (const action of ALL_ACTIONS) {
      expect(can(admin, action, { departmentId: "vehicle" }), action).toBe(action !== "request.create");
    }
  });

  it("sees every department", () => expect(visibleDepartments(admin)).toEqual(DEPARTMENT_IDS));
});

describe("visibleDepartments", () => {
  it("is empty for customers, nobody and inactive staff", () => {
    expect(visibleDepartments(null)).toEqual([]);
    expect(visibleDepartments(customer("c"))).toEqual([]);
    expect(visibleDepartments(staff("off", ["loan"], false))).toEqual([]);
  });
});

describe("canAssignTo", () => {
  const colleague = staff("colleague", ["loan"]);

  it("lets staff claim a request for themselves but not hand it to a colleague", () => {
    expect(canAssignTo(reza, reza, "loan")).toBe(true);
    expect(canAssignTo(reza, colleague, "loan")).toBe(false);
  });

  it("lets an administrator assign to any active staff member of that department", () => {
    expect(canAssignTo(admin, reza, "loan")).toBe(true);
    expect(canAssignTo(admin, colleague, "loan")).toBe(true);
  });

  it("never assigns outside the assignee's own departments", () => {
    expect(canAssignTo(admin, reza, "vehicle")).toBe(false);
    expect(canAssignTo(reza, reza, "vehicle")).toBe(false); // not even to himself: not his department
  });

  it("rejects customers, admins and deactivated staff as assignees", () => {
    expect(canAssignTo(admin, customer("c"), "loan")).toBe(false);
    expect(canAssignTo(admin, admin, "loan")).toBe(false);
    expect(canAssignTo(admin, staff("off", ["loan"], false), "loan")).toBe(false);
  });

  it("allows un-assigning only for someone who may assign in that department", () => {
    expect(canAssignTo(reza, null, "loan")).toBe(true);
    expect(canAssignTo(reza, null, "vehicle")).toBe(false);
    expect(canAssignTo(customer("c"), null, "loan")).toBe(false);
    expect(canAssignTo(null, null, "loan")).toBe(false);
  });
});
