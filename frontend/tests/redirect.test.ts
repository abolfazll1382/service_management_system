import { describe, expect, it } from "vitest";
import { loginUrl, safeNextPath } from "@/lib/auth/redirect";

describe("safeNextPath", () => {
  it("keeps same-site paths, with their query and hash", () => {
    expect(safeNextPath("/apply/personal-loan", "/services")).toBe("/apply/personal-loan");
    expect(safeNextPath("/my/requests?open=req-1#activity", "/services")).toBe("/my/requests?open=req-1#activity");
    expect(safeNextPath("/", "/services")).toBe("/");
  });

  it("falls back when there is nothing usable", () => {
    for (const value of [null, undefined, "", "services", "?x=1"]) {
      expect(safeNextPath(value, "/services")).toBe("/services");
    }
  });

  it("refuses anything that would leave the site", () => {
    const attacks = [
      "//evil.example",
      "//evil.example/path",
      "/\\evil.example",
      "/\\/evil.example",
      "/\t/evil.example", // browsers drop the tab: it becomes "//evil.example"
      "/\n/evil.example",
      "/\r/evil.example",
      "https://evil.example",
      "http://evil.example",
      "javascript:alert(1)",
      "data:text/html,hi",
    ];
    for (const attack of attacks) {
      expect(safeNextPath(attack, "/services"), attack).toBe("/services");
    }
  });

  it("normalises dot segments instead of passing them through", () => {
    expect(safeNextPath("/a/../b", "/services")).toBe("/b");
  });
});

describe("loginUrl", () => {
  it("encodes the return path so it survives as one parameter", () => {
    expect(loginUrl("/login", "/apply/x?y=1&z=2")).toBe("/login?next=%2Fapply%2Fx%3Fy%3D1%26z%3D2");
  });
});
