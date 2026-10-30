import { describe, expect, it } from "vitest";
import { verifyPassword } from "@/lib/auth/password";
import { findService } from "@/lib/catalog";
import { DEPARTMENT_IDS } from "@/types/department";
import { createSeedData, DEMO_PASSWORD } from "@/lib/store/seed";
import { isValidNationalId } from "@/lib/utils/persianUtils";
import { createDetailsSchema } from "@/lib/validation/request";
import { identityTranslate } from "@/lib/validation/fields";
import { ALLOWED_TRANSITIONS } from "@/lib/domain/workflow";

const seed = createSeedData();

describe("seed accounts", () => {
  it("accepts the documented demo password for every account (so a typo can't lock one out)", () => {
    for (const user of seed.users) {
      expect(verifyPassword(DEMO_PASSWORD, user.passwordSalt, user.passwordHash), user.id).toBe(true);
    }
  });

  it("has unique ids, usernames, national IDs and phone numbers", () => {
    const unique = (values: (string | undefined)[]) => new Set(values.filter(Boolean)).size === values.filter(Boolean).length;
    expect(unique(seed.users.map((user) => user.id))).toBe(true);
    expect(unique(seed.users.map((user) => ("username" in user ? user.username : undefined)))).toBe(true);
    expect(unique(seed.users.map((user) => ("nationalId" in user ? user.nationalId : undefined)))).toBe(true);
    expect(unique(seed.users.map((user) => ("phone" in user ? user.phone : undefined)))).toBe(true);
  });

  it("gives customers valid national IDs, and staff real departments", () => {
    for (const user of seed.users) {
      if (user.role === "customer") expect(isValidNationalId(user.nationalId), user.fullName).toBe(true);
      if (user.role === "staff") {
        expect(user.departmentIds.length, user.username).toBeGreaterThan(0);
        for (const department of user.departmentIds) expect(DEPARTMENT_IDS).toContain(department);
      }
    }
  });

  it("matches the departments described in the brief: Reza loans, Sara raw materials, Ali vehicles", () => {
    const departments = (username: string) =>
      seed.users.find((user) => user.role === "staff" && user.username === username && user);
    expect(departments("reza")).toMatchObject({ departmentIds: ["loan"] });
    expect(departments("sara")).toMatchObject({ departmentIds: ["raw_material"] });
    expect(departments("ali")).toMatchObject({ departmentIds: ["vehicle"] });
    expect(departments("maryam")).toMatchObject({ departmentIds: ["housing"] });
  });
});

describe("seed requests", () => {
  it("point at real customers and services, in the service's own department", () => {
    const customers = new Map(seed.users.filter((user) => user.role === "customer").map((user) => [user.id, user]));
    for (const request of seed.requests) {
      const service = findService(request.serviceId);
      expect(service, request.id).toBeDefined();
      expect(request.departmentId, request.id).toBe(service?.departmentId);
      expect(customers.has(request.customerId), request.id).toBe(true);
      expect(request.trackingCode, request.id).toMatch(/^\d{10}$/);
    }
    expect(new Set(seed.requests.map((request) => request.trackingCode)).size).toBe(seed.requests.length);
  });

  it("carry details that satisfy their service's own validator", () => {
    for (const request of seed.requests) {
      const service = findService(request.serviceId)!;
      const result = createDetailsSchema(service.fields, identityTranslate).safeParse(request.details);
      expect(result.success, `${request.id}: ${JSON.stringify(request.details)}`).toBe(true);
    }
  });

  it("have a coherent history: legal moves only, in time order, ending at the stored status", () => {
    for (const request of seed.requests) {
      expect(request.timeline[0].kind, request.id).toBe("submitted");
      let status = "pending_review";
      let previous = "";
      for (const event of request.timeline) {
        expect(event.at >= previous, `${request.id} out of order`).toBe(true);
        previous = event.at;
        if (event.kind === "status_changed") {
          expect(event.from, request.id).toBe(status);
          expect(ALLOWED_TRANSITIONS[event.from], `${request.id} ${event.from}→${event.to}`).toContain(event.to);
          status = event.to;
        }
      }
      expect(request.status, request.id).toBe(status);
      expect(request.updatedAt).toBe(request.timeline.at(-1)?.at);
    }
  });

  it("only assigns requests to staff who belong to that department", () => {
    for (const request of seed.requests) {
      if (!request.assignee) continue;
      const staff = seed.users.find((user) => user.id === request.assignee?.id);
      expect(staff?.role, request.id).toBe("staff");
      if (staff?.role === "staff") expect(staff.departmentIds, request.id).toContain(request.departmentId);
    }
  });

  it("covers every status and every department, so each screen has something to show", () => {
    expect(new Set(seed.requests.map((request) => request.status)).size).toBeGreaterThanOrEqual(5);
    expect(new Set(seed.requests.map((request) => request.departmentId))).toEqual(new Set(DEPARTMENT_IDS));
  });

  it("returns an independent copy each time, so resetting never shares live state", () => {
    const first = createSeedData();
    const second = createSeedData();
    first.users[0].isActive = false;
    first.requests[0].timeline.pop();
    expect(second.users[0].isActive).toBe(true);
    expect(second.requests[0].timeline.length).toBeGreaterThan(first.requests[0].timeline.length);
  });
});
