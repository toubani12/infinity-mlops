import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { session } from "@/test/fixtures";
import { resetSessionStoreForTests, SessionProvider, useSession } from "./SessionProvider";
import { loadSignOutReason, saveSession } from "./session";

function WhoAmI() {
  const { session: current } = useSession();
  return <p>{current ? `signed in as ${current.username}` : "signed out"}</p>;
}

describe("SessionProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetSessionStoreForTests();
  });
  afterEach(() => {
    vi.useRealTimers();
    window.sessionStorage.clear();
  });

  it("signs out when the token expires and remembers why", () => {
    saveSession(session({ expiresAt: new Date(Date.now() + 90_000).toISOString() }));
    render(
      <SessionProvider>
        <WhoAmI />
      </SessionProvider>,
    );
    expect(screen.getByText("signed in as ana")).toBeInTheDocument();

    act(() => vi.advanceTimersByTime(89_000));
    expect(screen.getByText("signed in as ana")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1_000));

    expect(screen.getByText("signed out")).toBeInTheDocument();
    expect(loadSignOutReason()).toBe("expired");
  });
});
