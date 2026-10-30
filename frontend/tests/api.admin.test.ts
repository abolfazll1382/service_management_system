import { describe, expect, it } from "vitest";
import { auditApi, authApi, catalogApi, demoApi, requestsApi, staffApi } from "@/lib/api";
import { readDb } from "@/lib/mock-server/db";
import { useSessionStore } from "@/lib/auth/sessionStore";
import { configureMockClient } from "@/lib/api";
import { DEMO_PASSWORD } from "@/lib/store/seed";
import {
  REQ,
  rejectsWith,
  signInCustomer,
  signInStaff,
  signOutLocally,
  resetBackendBeforeEach,
  validLoan,
} from "./helpers";

resetBackendBeforeEach();

describe("submitting a request", () => {
  it("files it under the service's department with a unique 10-digit tracking code", async () => {
    await signInCustomer("amir");
    const created = await requestsApi.create(validLoan);
    expect(created).toMatchObject({
      status: "pending_review",
      departmentId: "loan",
      serviceId: "personal-loan",
      assignee: null,
      customerId: "c-amir",
      customer: { nationalId: "0045813922", phone: "09121234567" },
    });
    expect(created.trackingCode).toMatch(/^\d{10}$/);
    expect(created.timeline).toHaveLength(1);
    expect(created.timeline[0]).toMatchObject({ kind: "submitted", actor: { id: "c-amir", role: "customer" } });

    const second = await requestsApi.create(validLoan);
    expect(second.trackingCode).not.toBe(created.trackingCode);
  });

  it("lands in the right department's queue and nobody else's", async () => {
    await signInCustomer("amir");
    const created = await requestsApi.create(validLoan);
    signOutLocally();

    await signInStaff("reza");
    expect((await requestsApi.queue({ search: created.trackingCode })).total).toBe(1);
    signOutLocally();
    for (const other of ["sara", "ali", "maryam"]) {
      await signInStaff(other);
      expect((await requestsApi.queue({ search: created.trackingCode })).total, other).toBe(0);
      signOutLocally();
    }
  });

  it("ignores fields the client has no business setting", async () => {
    await signInCustomer("amir");
    const created = await requestsApi.create({
      ...validLoan,
      customerId: "c-hossein",
      status: "approved",
      assignee: { id: "u-reza" },
      details: { ...validLoan.details, isPreApproved: "yes" },
    } as never);
    expect(created.customerId).toBe("c-amir");
    expect(created.status).toBe("pending_review");
    expect(created.assignee).toBeNull();
    expect(created.details).not.toHaveProperty("isPreApproved");
  });

  it("re-validates the service's own fields on the server", async () => {
    await signInCustomer("amir");
    await rejectsWith(requestsApi.create({ ...validLoan, details: { ...validLoan.details, amount: 5 } }), "validation");
    await rejectsWith(requestsApi.create({ ...validLoan, details: { ...validLoan.details, termMonths: "7" } }), "validation");
    await rejectsWith(requestsApi.create({ ...validLoan, details: { amount: 100_000_000 } }), "validation");
    await rejectsWith(requestsApi.create({ ...validLoan, description: "short" }), "validation");
    await rejectsWith(requestsApi.create({ ...validLoan, serviceId: "unknown-service" }), "not_found");
  });
});

describe("service availability", () => {
  it("is public to read and admin-only to change", async () => {
    const services = await catalogApi.listServices();
    expect(services).toHaveLength(8);
    expect(services.every((service) => service.isActive)).toBe(true);
    await rejectsWith(catalogApi.setServiceActive("personal-loan", false), "unauthenticated");
  });

  it("stops new requests for a switched-off service, and resumes when it is back on", async () => {
    await signInStaff("admin");
    await catalogApi.setServiceActive("personal-loan", false);
    expect((await catalogApi.getService("personal-loan")).isActive).toBe(false);
    signOutLocally();

    await signInCustomer("amir");
    await rejectsWith(requestsApi.create(validLoan), "service_unavailable");
    signOutLocally();

    await signInStaff("admin");
    await catalogApi.setServiceActive("personal-loan", true);
    signOutLocally();
    await signInCustomer("amir");
    await expect(requestsApi.create(validLoan)).resolves.toMatchObject({ status: "pending_review" });
    await rejectsWith(catalogApi.getService("nope"), "not_found");
  });
});

describe("team management (administrators only)", () => {
  const newStaff = {
    nameFa: "نیما احمدی",
    nameEn: "Nima Ahmadi",
    username: "nima",
    password: "Welcome1pass",
    departmentIds: ["vehicle"] as ("vehicle" | "loan" | "raw_material" | "housing")[],
  };

  it("lists accounts without any credentials", async () => {
    await signInStaff("admin");
    const accounts = await staffApi.list();
    expect(accounts.map((account) => account.role).sort()).toEqual(["admin", "staff", "staff", "staff", "staff"]);
    expect(JSON.stringify(accounts)).not.toMatch(/passwordHash|passwordSalt/);
  });

  it("creates staff who can sign in and are confined to the departments they were given", async () => {
    await signInStaff("admin");
    const created = await staffApi.create({ ...newStaff, role: "admin" } as never);
    expect(created).toMatchObject({ role: "staff", username: "nima", departmentIds: ["vehicle"], isActive: true });
    signOutLocally();

    useSessionStore.getState().signIn(await authApi.loginStaff({ username: "nima", password: newStaff.password }));
    const page = await requestsApi.queue();
    expect(page.items.every((request) => request.departmentId === "vehicle")).toBe(true);
    await rejectsWith(requestsApi.queue({ departmentId: "loan" }), "forbidden");
    await rejectsWith(staffApi.list(), "forbidden");
  });

  it("refuses duplicate usernames, weak passwords and accounts with no department", async () => {
    await signInStaff("admin");
    await rejectsWith(staffApi.create({ ...newStaff, username: "reza" }), "username_taken");
    await rejectsWith(staffApi.create({ ...newStaff, username: "admin" }), "username_taken");
    await rejectsWith(staffApi.create({ ...newStaff, password: "short1" }), "validation");
    await rejectsWith(staffApi.create({ ...newStaff, departmentIds: [] }), "validation");
    await rejectsWith(staffApi.create({ ...newStaff, username: "Bad Name" }), "validation");
  });

  it("changes a staff member's access immediately — no re-login needed — and un-assigns stranded work", async () => {
    const reza = await signInStaff("reza");
    expect((await requestsApi.queue()).total).toBe(2);
    signOutLocally();

    await signInStaff("admin");
    await staffApi.update(reza.user.id, { departmentIds: ["housing"], isActive: true });
    const stranded = await requestsApi.get(REQ.loanInProgress); // assigned to Reza, in the loan department he just lost
    expect(stranded.assignee).toBeNull();
    expect(stranded.timeline.at(-1)).toMatchObject({ kind: "assigned", assignee: null, actor: { role: "admin" } });
    signOutLocally();

    useSessionStore.getState().signIn(reza); // the SAME token he already held
    const page = await requestsApi.queue();
    expect(page.items.every((request) => request.departmentId === "housing")).toBe(true);
    await rejectsWith(requestsApi.get(REQ.loanInProgress), "forbidden");
  });

  it("deactivating someone signs them out, frees their open work and keeps closed history", async () => {
    const sara = await signInStaff("sara");
    signOutLocally();
    await signInStaff("admin");
    await staffApi.update(sara.user.id, { departmentIds: ["raw_material"], isActive: false });

    expect((await requestsApi.get(REQ.rawNeedsCorrection)).assignee).toBeNull(); // open → freed
    expect((await requestsApi.get(REQ.rawClosed)).assignee?.id).toBe("u-sara"); // closed → history kept

    await staffApi.update(sara.user.id, { departmentIds: ["raw_material"], isActive: true });
    signOutLocally();
    await expect(authApi.loginStaff({ username: "sara", password: DEMO_PASSWORD })).resolves.toBeDefined();
  });

  it("won't edit administrators, customers or unknown accounts", async () => {
    await signInStaff("admin");
    const edit = { departmentIds: ["loan" as const], isActive: false };
    await rejectsWith(staffApi.update("u-admin", edit), "forbidden");
    await rejectsWith(staffApi.update("c-amir", edit), "forbidden");
    await rejectsWith(staffApi.update("ghost", edit), "not_found");
    await rejectsWith(staffApi.update("u-reza", { departmentIds: [], isActive: true }), "validation");
  });
});

describe("audit log", () => {
  it("records pausing and resuming a service as separate events whose target carries no wording", async () => {
    await signInStaff("admin");
    await catalogApi.setServiceActive("steel-supply", false);
    await catalogApi.setServiceActive("steel-supply", true);
    const [resumed, paused] = (await auditApi.list()).items;
    expect(resumed).toMatchObject({ action: "service_resumed", target: "steel-supply" });
    expect(paused).toMatchObject({ action: "service_paused", target: "steel-supply" });
  });

  it("records who did what, newest first, and pages", async () => {
    await signInStaff("admin");
    await catalogApi.setServiceActive("steel-supply", false);
    await staffApi.create({ nameFa: "نیما", nameEn: "Nima", username: "nima", password: "Welcome1pass", departmentIds: ["loan"] });

    const page = await auditApi.list();
    expect(page.items.map((entry) => entry.action).slice(0, 3)).toEqual(["staff_created", "service_paused", "auth_login"]);
    expect(page.items[0]).toMatchObject({ target: "nima", actor: { id: "u-admin" } });
    expect(page.items[1].target).toBe("steel-supply");

    const small = await auditApi.list({ pageSize: 2, page: 2 });
    expect(small).toMatchObject({ total: page.total, page: 2, pageSize: 2 });
    expect(small.items).toHaveLength(Math.min(2, page.total - 2));
  });

  it("captures request activity without copying message text or personal details", async () => {
    await signInCustomer("amir");
    await requestsApi.addMessage(REQ.loanInProgress, { body: "My secret message body", visibility: "public" });
    signOutLocally();
    await signInStaff("admin");
    const { items } = await auditApi.list();
    expect(items.some((entry) => entry.action === "request_message_added")).toBe(true);
    const text = JSON.stringify(items);
    expect(text).not.toContain("My secret message body");
    expect(text).not.toContain("0045813922");
  });
});

describe("demo reset", () => {
  it("restores the seed data, ends other sessions, but keeps the administrator signed in", async () => {
    await signInCustomer("amir");
    const created = await requestsApi.create(validLoan);
    const amir = { ...useSessionStore.getState() };
    signOutLocally();

    await signInStaff("admin");
    expect(readDb().requests.some((request) => request.id === created.id)).toBe(true);
    await demoApi.reset();

    expect(readDb().requests).toHaveLength(8);
    expect(readDb().requests.some((request) => request.id === created.id)).toBe(false);
    await expect(authApi.me()).resolves.toMatchObject({ username: "admin" });
    expect((await auditApi.list()).items.map((entry) => entry.action)).toEqual(["demo_reset"]);

    useSessionStore.getState().signIn({ token: amir.token!, user: amir.user! });
    await rejectsWith(authApi.me(), "unauthenticated");
  });
});

describe("transport failures", () => {
  it("fail before reaching the server, so nothing is half-applied", async () => {
    await signInCustomer("amir");
    const before = readDb().requests.length;
    configureMockClient({ failureRate: 1 });
    await rejectsWith(requestsApi.create(validLoan), "network");
    configureMockClient({ failureRate: 0 });
    expect(readDb().requests).toHaveLength(before);
  });
});
