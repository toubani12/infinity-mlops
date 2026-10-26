import { afterEach, describe, expect, it } from "vitest";
import { session } from "@/test/fixtures";
import { clearSession, isExpired, loadSession, saveSession } from "./session";

describe("session storage", () => {
  afterEach(() => window.sessionStorage.clear());

  it("round-trips a valid session", () => {
    const current = session();
    saveSession(current);

    expect(loadSession()).toEqual(current);
  });

  it("drops expired sessions", () => {
    saveSession(session({ expiresAt: "2026-10-26T08:00:00Z" }));

    expect(loadSession(Date.parse("2026-10-26T09:00:00Z"))).toBeNull();
    expect(window.sessionStorage.length).toBe(0);
  });

  it("ignores corrupt storage and clears on sign out", () => {
    window.sessionStorage.setItem("infinity.session", "{oops");
    expect(loadSession()).toBeNull();

    saveSession(session());
    clearSession();
    expect(loadSession()).toBeNull();
  });

  it("compares expiry with the given clock", () => {
    const current = session({ expiresAt: "2026-10-26T10:00:00Z" });
    expect(isExpired(current, Date.parse("2026-10-26T09:59:59Z"))).toBe(false);
    expect(isExpired(current, Date.parse("2026-10-26T10:00:00Z"))).toBe(true);
  });
});
