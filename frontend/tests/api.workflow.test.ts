import { describe, expect, it } from "vitest";
import { requestsApi, staffApi } from "@/lib/api";
import { readDb } from "@/lib/mock-server/db";
import {
  REQ,
  rejectsWith,
  signInCustomer,
  signInStaff,
  signOutLocally,
  resetBackendBeforeEach,
} from "./helpers";

resetBackendBeforeEach();

const kinds = (request: { timeline: { kind: string }[] }) => request.timeline.map((event) => event.kind);

describe("processing a request", () => {
  it("starting a review moves it to in-progress AND claims it for the staff member", async () => {
    await signInStaff("reza");
    const before = (await requestsApi.get(REQ.loanPending)).timeline.length;
    const updated = await requestsApi.transition(REQ.loanPending, { to: "in_progress" });

    expect(updated.status).toBe("in_progress");
    expect(updated.assignee).toMatchObject({ id: "u-reza", role: "staff" });
    expect(kinds(updated).slice(before)).toEqual(["assigned", "status_changed"]);
    const change = updated.timeline.at(-1);
    expect(change).toMatchObject({ kind: "status_changed", from: "pending_review", to: "in_progress" });
    expect(change?.actor.id).toBe("u-reza");
  });

  it("walks the happy path and refuses to skip review", async () => {
    await signInStaff("reza");
    await rejectsWith(requestsApi.transition(REQ.loanPending, { to: "approved" }), "invalid_transition");
    await requestsApi.transition(REQ.loanPending, { to: "in_progress" });
    await requestsApi.transition(REQ.loanPending, { to: "approved", note: "Approved for 24 months." });
    const closed = await requestsApi.transition(REQ.loanPending, { to: "closed" });
    expect(closed.status).toBe("closed");
    await rejectsWith(requestsApi.transition(REQ.loanPending, { to: "in_progress" }), "request_closed");
  });

  it("requires a reason to reject or ask for corrections, and shows it to the applicant", async () => {
    await signInStaff("reza");
    await rejectsWith(requestsApi.transition(REQ.loanPending, { to: "rejected" }), "validation");
    await rejectsWith(requestsApi.transition(REQ.loanPending, { to: "rejected", note: "   " }), "validation");
    expect(readDb().requests.find((r) => r.id === REQ.loanPending)?.status).toBe("pending_review"); // nothing changed

    await requestsApi.transition(REQ.loanPending, { to: "rejected", note: "Income documents are missing." });
    signOutLocally();
    await signInCustomer("hossein");
    const seen = await requestsApi.get(REQ.loanPending);
    expect(seen.status).toBe("rejected");
    expect(seen.timeline.at(-1)).toMatchObject({ kind: "message", visibility: "public", body: "Income documents are missing." });
  });

  it("rejects an invalid or unknown target status", async () => {
    await signInStaff("reza");
    await rejectsWith(requestsApi.transition(REQ.loanPending, { to: "teleported" as never }), "validation");
    await rejectsWith(requestsApi.transition("req-nope", { to: "in_progress" }), "not_found");
  });
});

describe("closed requests are frozen", () => {
  it("accepts no status change, assignment or message from anyone", async () => {
    await signInStaff("sara");
    await rejectsWith(requestsApi.transition(REQ.rawClosed, { to: "in_progress" }), "request_closed");
    await rejectsWith(requestsApi.assign(REQ.rawClosed, "u-sara"), "request_closed");
    await rejectsWith(requestsApi.addMessage(REQ.rawClosed, { body: "late", visibility: "public" }), "request_closed");
    signOutLocally();
    await signInCustomer("hossein");
    await rejectsWith(requestsApi.addMessage(REQ.rawClosed, { body: "late", visibility: "public" }), "request_closed");
  });
});

describe("messages and the correction loop", () => {
  it("an applicant's reply to a correction request hands the request back to staff", async () => {
    await signInCustomer("maryam");
    const updated = await requestsApi.addMessage(REQ.rawNeedsCorrection, { body: "The project number is 42.", visibility: "public" });

    expect(updated.status).toBe("in_progress");
    expect(kinds(updated).slice(-2)).toEqual(["message", "status_changed"]);
    expect(updated.timeline.at(-1)?.actor.role).toBe("customer"); // recorded as THEIR action
    // ...without having gained the right to change statuses themselves:
    await rejectsWith(requestsApi.transition(REQ.rawNeedsCorrection, { to: "approved" }), "forbidden");
  });

  it("a reply on any other open request leaves the status alone", async () => {
    await signInCustomer("amir");
    const updated = await requestsApi.addMessage(REQ.loanInProgress, { body: "Any news?", visibility: "public" });
    expect(updated.status).toBe("in_progress");
    expect(kinds(updated).at(-1)).toBe("message");
  });

  it("validates the message body", async () => {
    await signInCustomer("amir");
    await rejectsWith(requestsApi.addMessage(REQ.loanInProgress, { body: "   ", visibility: "public" }), "validation");
    await rejectsWith(requestsApi.addMessage(REQ.loanInProgress, { body: "x".repeat(1001), visibility: "public" }), "validation");
    await rejectsWith(requestsApi.addMessage(REQ.loanInProgress, { body: "ok", visibility: "secret" as never }), "validation");
  });
});

describe("assignment", () => {
  it("lets staff claim a request in their department, and release it", async () => {
    await signInStaff("reza");
    const claimed = await requestsApi.assign(REQ.loanPending, "u-reza");
    expect(claimed.assignee?.id).toBe("u-reza");
    expect(claimed.timeline.at(-1)).toMatchObject({ kind: "assigned", assignee: { id: "u-reza" } });

    const released = await requestsApi.assign(REQ.loanPending, null);
    expect(released.assignee).toBeNull();
  });

  it("adds nothing to the history when the assignee doesn't change", async () => {
    await signInStaff("reza");
    const before = (await requestsApi.get(REQ.loanInProgress)).timeline.length; // already Reza's
    const again = await requestsApi.assign(REQ.loanInProgress, "u-reza");
    expect(again.timeline).toHaveLength(before);
  });

  it("only lets an administrator hand work to a colleague", async () => {
    await signInStaff("admin");
    const colleague = await staffApi.create({
      nameFa: "نیما",
      nameEn: "Nima",
      username: "nima",
      password: "Welcome1pass",
      departmentIds: ["loan"],
    });
    signOutLocally();

    await signInStaff("reza");
    await rejectsWith(requestsApi.assign(REQ.loanPending, colleague.id), "forbidden");
    expect((await requestsApi.assignableStaff("loan")).map((actor) => actor.id)).toEqual(["u-reza"]);
    signOutLocally();

    await signInStaff("admin");
    const handed = await requestsApi.assign(REQ.loanPending, colleague.id);
    expect(handed.assignee?.id).toBe(colleague.id);
    expect((await requestsApi.assignableStaff("loan")).map((actor) => actor.id).sort()).toEqual(["u-reza", colleague.id].sort());
  });

  it("never assigns outside the assignee's department, or to a non-staff account", async () => {
    await signInStaff("admin");
    await rejectsWith(requestsApi.assign(REQ.loanPending, "u-sara"), "forbidden"); // raw materials ≠ loans
    await rejectsWith(requestsApi.assign(REQ.loanPending, "c-amir"), "forbidden"); // a customer
    await rejectsWith(requestsApi.assign(REQ.loanPending, "u-admin"), "forbidden"); // not a staff role
    await rejectsWith(requestsApi.assign(REQ.loanPending, "no-such-user"), "not_found");
  });
});
