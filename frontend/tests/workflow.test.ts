import { describe, expect, it } from "vitest";
import { ALLOWED_TRANSITIONS, canTransition, isClosed, isOpen, nextStatuses, requiresNote } from "@/lib/domain/workflow";
import { REQUEST_STATUSES } from "@/types/request";

describe("status workflow", () => {
  it("defines moves for every status, and only to real statuses", () => {
    expect(Object.keys(ALLOWED_TRANSITIONS).sort()).toEqual([...REQUEST_STATUSES].sort());
    for (const targets of Object.values(ALLOWED_TRANSITIONS)) {
      for (const target of targets) expect(REQUEST_STATUSES).toContain(target);
    }
  });

  it("never allows a status to move to itself", () => {
    for (const status of REQUEST_STATUSES) expect(canTransition(status, status)).toBe(false);
  });

  it("makes 'closed' terminal", () => {
    expect(nextStatuses("closed")).toEqual([]);
    expect(isClosed("closed")).toBe(true);
  });

  it("can't skip review: pending requests don't jump straight to approved", () => {
    expect(canTransition("pending_review", "approved")).toBe(false);
    expect(canTransition("pending_review", "in_progress")).toBe(true);
    expect(canTransition("in_progress", "approved")).toBe(true);
  });

  it("lets every non-terminal status eventually reach 'closed'", () => {
    const reachable = (from: (typeof REQUEST_STATUSES)[number], seen = new Set<string>()): boolean => {
      if (from === "closed") return true;
      if (seen.has(from)) return false;
      seen.add(from);
      return nextStatuses(from).some((next) => reachable(next, seen));
    };
    for (const status of REQUEST_STATUSES) expect(reachable(status), status).toBe(true);
  });

  it("treats exactly the three working statuses as open", () => {
    expect(REQUEST_STATUSES.filter(isOpen).sort()).toEqual(["in_progress", "needs_correction", "pending_review"]);
  });

  it("requires a reason for rejections and correction requests only", () => {
    expect(REQUEST_STATUSES.filter(requiresNote).sort()).toEqual(["needs_correction", "rejected"]);
  });
});
