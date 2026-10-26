import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider } from "@/lib/auth";
import { resetSessionStoreForTests } from "@/lib/auth/SessionProvider";
import { saveSession } from "@/lib/auth/session";
import { FakeEventSource } from "@/test/FakeEventSource";
import { jsonResponse, page, session, transaction } from "@/test/fixtures";
import { LiveTransactions } from "./LiveTransactions";

describe("LiveTransactions", () => {
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

  function renderLive() {
    render(
      <SessionProvider>
        <LiveTransactions />
      </SessionProvider>,
    );
  }

  it("loads recent transactions then prepends streamed scores", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(page([transaction({ transactionId: "11111111-aaaa", fraudScore: 0.02, isFraud: false })])),
    );
    renderLive();

    expect(await screen.findByText("11111111")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({ Authorization: "Bearer jwt-token" });
    expect(FakeEventSource.latest().url).toContain("/api/stream/transactions?access_token=jwt-token");

    act(() => {
      FakeEventSource.latest().open();
      FakeEventSource.latest().emit(
        "transaction",
        transaction({ transactionId: "22222222-bbbb", fraudScore: 0.97, isFraud: true, modelVersion: "4" }),
      );
    });

    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("22222222")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Fraud")).toBeInTheDocument();
    expect(within(rows[0]).getByText("v4")).toBeInTheDocument();
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("filters by id and reloads fraud only from the api", async () => {
    fetchMock.mockImplementation(async () =>
      jsonResponse(
        page([
          transaction({ transactionId: "aaaa0000-1", fraudScore: 0.95, isFraud: true }),
          transaction({ transactionId: "bbbb0000-2", fraudScore: 0.05, isFraud: false }),
        ]),
      ),
    );
    renderLive();
    await screen.findByText("aaaa0000");

    await userEvent.type(screen.getByPlaceholderText("Search by transaction id"), "bbbb");
    expect(screen.queryByText("aaaa0000")).not.toBeInTheDocument();
    expect(screen.getByText("bbbb0000")).toBeInTheDocument();

    await userEvent.clear(screen.getByPlaceholderText("Search by transaction id"));
    await userEvent.click(screen.getByLabelText("Fraud only"));
    expect(String(fetchMock.mock.calls.at(-1)?.[0])).toContain("fraudOnly=true");
    expect(screen.queryByText("bbbb0000")).not.toBeInTheDocument();
  });

  it("signs out when the token is rejected", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 401 }, 401));
    renderLive();

    await vi.waitFor(() => expect(window.sessionStorage.getItem("infinity.session")).toBeNull());
  });

  it("reloads the latest page after a reconnect so missed rows appear", async () => {
    const pages = [
      page([transaction({ transactionId: "aaaa0000-1" })]),
      page([
        transaction({ transactionId: "bbbb0000-2", receivedAt: "2026-10-26T09:16:00Z" }),
        transaction({ transactionId: "aaaa0000-1" }),
      ]),
    ];
    fetchMock.mockImplementation(async (input) =>
      String(input).includes("/api/stream/") ? new Response(null, { status: 200 }) : jsonResponse(pages.shift()),
    );
    renderLive();
    await screen.findByText("aaaa0000");

    act(() => {
      FakeEventSource.latest().open();
      FakeEventSource.latest().fail();
    });
    expect(screen.getByText(/Reconnecting in/)).toBeInTheDocument();
    await vi.waitFor(() => expect(FakeEventSource.instances).toHaveLength(2), { timeout: 3000 });
    act(() => FakeEventSource.latest().open());

    expect(await screen.findByText("bbbb0000")).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/transactions?size=100"))).toHaveLength(2);
    expect(screen.getAllByRole("row")).toHaveLength(3);
  });

  it("signs out with an expiry notice when the stream token is rejected", async () => {
    fetchMock.mockImplementation(async (input) =>
      String(input).includes("/api/stream/")
        ? new Response(null, { status: 401 })
        : jsonResponse(page([transaction()])),
    );
    renderLive();
    await screen.findByText("7f8d4c2e");

    act(() => FakeEventSource.latest().fail());

    await vi.waitFor(() => expect(window.sessionStorage.getItem("infinity.session")).toBeNull());
    expect(window.sessionStorage.getItem("infinity.signout")).toBe("expired");
  });
});
