import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Alert } from "@/lib/api";
import { SessionProvider } from "@/lib/auth";
import { resetSessionStoreForTests } from "@/lib/auth/SessionProvider";
import { saveSession } from "@/lib/auth/session";
import { FakeEventSource } from "@/test/FakeEventSource";
import { jsonResponse, page, session } from "@/test/fixtures";
import { AlertsBoard } from "./AlertsBoard";

const openAlert: Alert = {
  id: "alert-1",
  transactionId: "aaaa1111-2222",
  fraudScore: 0.93,
  status: "OPEN",
  createdAt: "2026-10-26T10:00:00Z",
  updatedAt: "2026-10-26T10:00:00Z",
};

describe("AlertsBoard", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    resetSessionStoreForTests();
    saveSession(session());
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", FakeEventSource);
    FakeEventSource.reset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    window.sessionStorage.clear();
  });

  function renderBoard() {
    render(
      <SessionProvider>
        <AlertsBoard />
      </SessionProvider>,
    );
  }

  it("acknowledges an open alert and drops it from the open view", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(page([openAlert])))
      .mockResolvedValueOnce(jsonResponse({ ...openAlert, status: "ACKNOWLEDGED" }));
    renderBoard();

    await userEvent.click(await screen.findByRole("button", { name: "Acknowledge alert on aaaa1111" }));

    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/alerts?status=OPEN");
    const [url, init] = fetchMock.mock.calls[1];
    expect(String(url)).toContain("/api/alerts/alert-1");
    expect(init?.method).toBe("PATCH");
    expect(init?.body).toBe(JSON.stringify({ status: "ACKNOWLEDGED" }));
    expect(screen.queryByText("aaaa1111")).not.toBeInTheDocument();
    expect(screen.getByText("No alerts to review")).toBeInTheDocument();
  });

  it("shows the server reason when an update is refused", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(page([openAlert])))
      .mockResolvedValueOnce(jsonResponse({ status: 409, detail: "Alert alert-1 is CLOSED and cannot move" }, 409));
    renderBoard();

    await userEvent.click(await screen.findByRole("button", { name: "Close alert on aaaa1111" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("is CLOSED and cannot move");
    expect(screen.getByText("aaaa1111")).toBeInTheDocument();
  });

  it("adds streamed alerts and switches views", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(page([]))).mockResolvedValueOnce(jsonResponse(page([])));
    renderBoard();
    await screen.findByText("No alerts to review");

    act(() => FakeEventSource.latest().emit("alert", { ...openAlert, id: "alert-2", transactionId: "bbbb2222-3333" }));
    expect(screen.getByText("bbbb2222")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Closed" }));
    expect(String(fetchMock.mock.calls[1][0])).toContain("status=CLOSED");
    expect(screen.getByRole("button", { name: "Closed" })).toHaveAttribute("aria-pressed", "true");
  });
});
