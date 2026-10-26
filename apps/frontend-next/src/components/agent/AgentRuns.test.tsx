import { act, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeEventSource } from "@/test/FakeEventSource";
import { agentRun, jsonResponse, page, RUN_ID } from "@/test/fixtures";
import { renderWithSession } from "@/test/renderWithSession";
import { AgentRuns } from "./AgentRuns";

function renderAs(ui: React.ReactNode, role: "admin" | "analyst") {
  return renderWithSession(ui, { role, username: role === "admin" ? "badr" : "ana" });
}

describe("agent runs list", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("EventSource", FakeEventSource);
    FakeEventSource.reset();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists runs with status badges and follows the stream", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(page([agentRun(), agentRun({ runId: "r-old", status: "NOISE", startedAt: "2026-10-25T08:00:00Z" })])),
    );
    renderAs(<AgentRuns />, "analyst");

    const links = await screen.findAllByRole("link");
    expect(links[0]).toHaveAttribute("href", `/agent/${RUN_ID}`);
    expect(within(links[0]).getByText("Awaiting approval")).toBeInTheDocument();
    expect(within(links[1]).getByText("Noise")).toBeInTheDocument();
    expect(screen.getByText("1 run waits for an admin decision.")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/agent/runs?size=50");

    act(() => FakeEventSource.latest().emit("agent", { run: agentRun({ status: "PROMOTED" }), event: null }));
    expect(within(screen.getAllByRole("link")[0]).getByText("Promoted")).toBeInTheDocument();
    expect(screen.getByText("No run is waiting for a decision.")).toBeInTheDocument();
  });

  it("shows an empty state and load errors", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(page([])));
    const { unmount } = renderAs(<AgentRuns />, "analyst");
    expect(await screen.findByText("No agent runs")).toBeInTheDocument();
    unmount();

    fetchMock.mockResolvedValueOnce(jsonResponse({ status: 500, detail: "database down" }, 500));
    renderAs(<AgentRuns />, "analyst");
    expect(await screen.findByRole("alert")).toHaveTextContent("database down");
  });
});
