import { describe, expect, it } from "vitest";
import { auditApi, authApi, catalogApi, demoApi, requestsApi, staffApi } from "@/lib/api";
import { readDb } from "@/lib/mock-server/db";
import { DEPARTMENT_IDS, type DepartmentId } from "@/types/department";
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

const idsOf = (page: { items: { id: string }[] }) => page.items.map((item) => item.id).sort();

describe("staff only ever see their own department's queue", () => {
  const expected: [string, DepartmentId, string[]][] = [
    ["reza", "loan", [REQ.loanInProgress, REQ.loanPending]],
    ["sara", "raw_material", [REQ.rawNeedsCorrection, REQ.rawClosed]],
    ["ali", "vehicle", [REQ.vehiclePending, REQ.vehicleRejected]],
    ["maryam", "housing", [REQ.housingApproved, REQ.housingInProgress]],
  ];

  it.each(expected)("%s sees only %s requests", async (username, department, ids) => {
    await signInStaff(username);
    const page = await requestsApi.queue();
    expect(idsOf(page)).toEqual([...ids].sort());
    expect(page.items.every((request) => request.departmentId === department)).toBe(true);
    expect(page.total).toBe(2);
    expect(Object.values(page.counts).reduce((a, b) => a + b, 0)).toBe(2);
  });

  it("refuses an explicit request for another department's queue", async () => {
    await signInStaff("reza");
    for (const other of DEPARTMENT_IDS.filter((id) => id !== "loan")) {
      await rejectsWith(requestsApi.queue({ departmentId: other }), "forbidden");
    }
    await expect(requestsApi.queue({ departmentId: "loan" })).resolves.toMatchObject({ total: 2 });
  });

  it("can't be widened by search: another department's tracking code finds nothing", async () => {
    await signInStaff("reza");
    const vehicleCode = readDb().requests.find((request) => request.id === REQ.vehiclePending)!.trackingCode;
    expect((await requestsApi.queue({ search: vehicleCode })).total).toBe(0);
    signOutLocally();
    await signInStaff("admin");
    expect((await requestsApi.queue({ search: vehicleCode })).total).toBe(1);
  });

  it("lets an administrator see every department", async () => {
    await signInStaff("admin");
    const page = await requestsApi.queue({ pageSize: 50 });
    expect(page.total).toBe(8);
    expect(new Set(page.items.map((request) => request.departmentId))).toEqual(new Set(DEPARTMENT_IDS));
  });

  it("filters, searches and pages inside the scope", async () => {
    await signInStaff("admin");
    expect((await requestsApi.queue({ status: "pending_review" })).total).toBe(2);
    expect((await requestsApi.queue({ assignment: "unassigned" })).total).toBe(2);
    expect((await requestsApi.queue({ search: "Hossein" })).total).toBe(3);
    expect((await requestsApi.queue({ search: "۰۵۹۲۸۴۶۷۱۷" })).total).toBe(3); // Persian digits
    const second = await requestsApi.queue({ pageSize: 3, page: 2 });
    expect(second).toMatchObject({ total: 8, page: 2, pageSize: 3 });
    expect(second.items).toHaveLength(3);
    expect((await requestsApi.queue({ pageSize: 3, page: 3 })).items).toHaveLength(2);
  });

  it("keeps status counts independent of the status filter", async () => {
    await signInStaff("admin");
    const all = await requestsApi.queue();
    const onlyPending = await requestsApi.queue({ status: "pending_review" });
    expect(onlyPending.counts).toEqual(all.counts);
    expect(onlyPending.items).toHaveLength(2);
  });
});

describe("staff cannot act on another department's request", () => {
  it("is refused for read, transition, assignment and messages, and nothing changes", async () => {
    await signInStaff("reza");
    const before = JSON.stringify(readDb().requests);

    await rejectsWith(requestsApi.get(REQ.vehiclePending), "forbidden");
    await rejectsWith(requestsApi.transition(REQ.vehiclePending, { to: "in_progress" }), "forbidden");
    await rejectsWith(requestsApi.assign(REQ.vehiclePending, "u-reza"), "forbidden");
    await rejectsWith(requestsApi.addMessage(REQ.vehiclePending, { body: "hello", visibility: "public" }), "forbidden");
    await rejectsWith(requestsApi.addMessage(REQ.vehiclePending, { body: "note", visibility: "internal" }), "forbidden");
    await rejectsWith(requestsApi.assignableStaff("vehicle"), "forbidden");

    expect(JSON.stringify(readDb().requests)).toBe(before);
  });

  it("applies to every pair of departments", async () => {
    const owner: Record<string, DepartmentId> = { reza: "loan", sara: "raw_material", ali: "vehicle", maryam: "housing" };
    const byDepartment = (department: DepartmentId) => readDb().requests.filter((r) => r.departmentId === department);
    for (const [username, own] of Object.entries(owner)) {
      signOutLocally();
      await signInStaff(username);
      for (const department of DEPARTMENT_IDS) {
        for (const request of byDepartment(department)) {
          const attempt = requestsApi.get(request.id);
          if (department === own) await expect(attempt).resolves.toMatchObject({ id: request.id });
          else await rejectsWith(attempt, "forbidden");
        }
      }
    }
  });

  it("does not offer staff the administration endpoints", async () => {
    await signInStaff("reza");
    await rejectsWith(staffApi.list(), "forbidden");
    await rejectsWith(auditApi.list(), "forbidden");
    await rejectsWith(demoApi.reset(), "forbidden");
    await rejectsWith(catalogApi.setServiceActive("personal-loan", false), "forbidden");
    await rejectsWith(requestsApi.create(validLoan), "forbidden");
  });
});

describe("customers see only their own requests", () => {
  it("lists just the caller's requests", async () => {
    await signInCustomer("amir");
    const mine = await requestsApi.listMine();
    expect(mine.map((request) => request.id).sort()).toEqual([REQ.loanInProgress, REQ.vehiclePending, REQ.housingInProgress].sort());
  });

  it("answers 'not found' for somebody else's request, however it is reached", async () => {
    await signInCustomer("maryam");
    await rejectsWith(requestsApi.get(REQ.loanInProgress), "not_found");
    await rejectsWith(requestsApi.addMessage(REQ.loanInProgress, { body: "hi", visibility: "public" }), "not_found");
    await rejectsWith(requestsApi.transition(REQ.loanInProgress, { to: "approved" }), "not_found");
    await rejectsWith(requestsApi.get("does-not-exist"), "not_found"); // same answer as a real-but-foreign id
  });

  it("cannot act as staff on their own request", async () => {
    await signInCustomer("amir");
    await rejectsWith(requestsApi.transition(REQ.loanInProgress, { to: "approved" }), "forbidden");
    await rejectsWith(requestsApi.assign(REQ.loanInProgress, "u-reza"), "forbidden");
    await rejectsWith(requestsApi.addMessage(REQ.loanInProgress, { body: "note", visibility: "internal" }), "forbidden");
    await rejectsWith(requestsApi.queue(), "forbidden");
    await rejectsWith(requestsApi.assignableStaff("loan"), "forbidden");
    await rejectsWith(staffApi.list(), "forbidden");
    await rejectsWith(auditApi.list(), "forbidden");
    await rejectsWith(demoApi.reset(), "forbidden");
  });

  it("is refused when not signed in at all", async () => {
    await rejectsWith(requestsApi.listMine(), "unauthenticated");
    await rejectsWith(requestsApi.create(validLoan), "unauthenticated");
    await rejectsWith(requestsApi.queue(), "unauthenticated");
    await rejectsWith(requestsApi.get(REQ.loanInProgress), "unauthenticated");
    await expect(catalogApi.listServices()).resolves.toHaveLength(8); // browsing the catalog is public
    await expect(authApi.me()).rejects.toMatchObject({ code: "unauthenticated" });
  });
});

describe("administrators", () => {
  it("run the system but can't file requests as an applicant", async () => {
    await signInStaff("admin");
    await rejectsWith(requestsApi.create(validLoan), "forbidden");
    await expect(requestsApi.listMine()).rejects.toMatchObject({ code: "forbidden" });
  });
});

describe("internal staff notes", () => {
  it("never reach the applicant, in any response", async () => {
    await signInCustomer("maryam");
    const detail = await requestsApi.get(REQ.housingApproved);
    expect(detail.timeline.some((event) => event.kind === "message" && event.visibility === "internal")).toBe(false);
    expect(JSON.stringify(detail)).not.toContain("household register");

    const mine = await requestsApi.listMine();
    expect(JSON.stringify(mine)).not.toContain("household register");
  });

  it("are visible to the department's staff and to administrators", async () => {
    for (const username of ["maryam", "admin"]) {
      signOutLocally();
      await signInStaff(username);
      const detail = await requestsApi.get(REQ.housingApproved);
      expect(JSON.stringify(detail)).toContain("household register");
    }
  });

  it("stay hidden from the applicant when staff add new ones", async () => {
    await signInStaff("sara");
    await requestsApi.addMessage(REQ.rawNeedsCorrection, { body: "Secret staff remark", visibility: "internal" });
    await requestsApi.addMessage(REQ.rawNeedsCorrection, { body: "Visible to applicant", visibility: "public" });
    signOutLocally();
    await signInCustomer("maryam");
    const text = JSON.stringify(await requestsApi.get(REQ.rawNeedsCorrection));
    expect(text).toContain("Visible to applicant");
    expect(text).not.toContain("Secret staff remark");
  });
});
