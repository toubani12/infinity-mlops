import { act, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeEventSource } from "@/test/FakeEventSource";
import { agentEvent, agentRun, agentRunDetail, jsonResponse, RUN_ID } from "@/test/fixtures";
import { renderWithSession } from "@/test/renderWithSession";
import { AgentRunView } from "./AgentRunView";

const params = vi.hoisted(() => ({ runId: "5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e" }));
vi.mock("next/navigation", () => ({ useParams: () => params }));

function renderAs(ui: React.ReactNode, role: "admin" | "analyst") {
  return renderWithSession(ui, { role, username: role === "admin" ? "badr" : "ana" });
}

describe("agent run approval", () => {
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

  it("shows the timeline and highlights the gate for a waiting run", async () => {
    fetchMock.mockResolvedValue(jsonResponse(agentRunDetail()));
    renderAs(<AgentRunView />, "analyst");

    expect(await screen.findByText("This promotion waits for a decision")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain(`/api/agent/runs/${RUN_ID}`);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText(/Only an admin can approve/)).toBeInTheDocument();
    const prAuc = screen.getByRole("row", { name: /PR-AUC/ });
    expect(within(prAuc).getByText("+0.120")).toBeInTheDocument();
    expect(within(prAuc).getByText("Above champion, met")).toHaveAttribute("data-passes", "true");
    expect(screen.getByText("Under 50 ms, met")).toBeInTheDocument();
    expect(screen.getByText("Approval requested")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "drift report 1c9e6f50" })).toHaveAttribute(
      "href",
      "/drift/1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f",
    );

    act(() =>
      FakeEventSource.latest().emit("agent", {
        run: agentRun({ status: "REJECTED", decidedBy: "badr", decisionReason: "too slow" }),
        event: agentEvent(5, "rejected", { decision: "keep_champion", message: "reject by badr: too slow" }),
      }),
    );
    expect(screen.getByText("reject by badr: too slow")).toBeInTheDocument();
    expect(screen.getByText(/Rejected by/)).toHaveTextContent("Rejected by badr: too slow");
  });

  it("lets an admin approve after confirming", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(agentRunDetail()))
      .mockResolvedValueOnce(
        jsonResponse(
          agentRun({
            pendingCommand: { commandId: "c1", action: "approve", actor: "badr", reason: null, sentAt: "2026-10-26T10:08:00Z" },
          }),
        ),
      );
    renderAs(<AgentRunView />, "admin");

    await user.click(await screen.findByRole("button", { name: "Approve" }));
    const dialog = screen.getByRole("dialog", { name: "Promote v4 to champion" });
    await user.click(within(dialog).getByRole("button", { name: "Approve" }));

    expect(await screen.findByText(/Waiting for the agent to confirm/)).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[1];
    expect(String(url)).toContain(`/api/agent/runs/${RUN_ID}/approve`);
    expect(init?.method).toBe("POST");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  });

  it("requires a reason to reject and reports conflicts", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(agentRunDetail()))
      .mockResolvedValueOnce(jsonResponse({ status: 409, detail: "A decision was already sent" }, 409))
      .mockResolvedValueOnce(jsonResponse(agentRunDetail({ run: agentRun({ status: "PROMOTED", decidedBy: "sara" }) })));
    renderAs(<AgentRunView />, "admin");

    await user.click(await screen.findByRole("button", { name: "Reject" }));
    const dialog = screen.getByRole("dialog", { name: "Reject v4" });
    const submit = within(dialog).getByRole("button", { name: "Reject" });
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Reason/), "  no");
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Reason/), "t now");
    await user.click(submit);

    expect(await screen.findByRole("alert")).toHaveTextContent("A decision was already sent. The run was reloaded.");
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({ reason: "not now" });
    expect(await screen.findByText(/Approved by/)).toHaveTextContent("Approved by sara.");
  });

  it("closes the dialog on cancel and keeps it open when the broker is down", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(agentRunDetail()))
      .mockResolvedValueOnce(jsonResponse({ status: 503, detail: "The decision could not be delivered" }, 503));
    renderAs(<AgentRunView />, "admin");

    await user.click(await screen.findByRole("button", { name: "Reject" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Approve" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be delivered");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("says when a run does not exist", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 404, detail: "Agent run x not found" }, 404));
    renderAs(<AgentRunView />, "analyst");

    expect(await screen.findByRole("alert")).toHaveTextContent("does not exist");
  });
});
