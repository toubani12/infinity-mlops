import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { driftReport, jsonResponse, page } from "@/test/fixtures";
import { renderWithSession } from "@/test/renderWithSession";
import { DriftReportDetail } from "./DriftReportDetail";
import { DriftReports } from "./DriftReports";

const params = vi.hoisted(() => ({ reportId: "1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f" }));
vi.mock("next/navigation", () => ({ useParams: () => params }));

describe("drift panel", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists reports with gauge, chips and quality gap", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(page([driftReport(), driftReport({ reportId: "r2", driftShare: 0.1, prAuc: null })])),
    );
    renderWithSession(<DriftReports />);

    const links = await screen.findAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "/drift/1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f");
    const first = within(links[0]);
    expect(first.getByRole("meter")).toHaveAttribute("aria-valuenow", "36");
    expect(first.getByText("amount")).toBeInTheDocument();
    expect(first.getByText("−13.0 pts")).toHaveClass("text-risk");
    expect(within(links[1]).getByText("No labels yet")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/drift/reports?size=50");
  });

  it("shows an empty state without reports", async () => {
    fetchMock.mockResolvedValue(jsonResponse(page([])));
    renderWithSession(<DriftReports />);

    expect(await screen.findByText("No drift reports yet")).toBeInTheDocument();
  });

  it("renders one report in detail", async () => {
    fetchMock.mockResolvedValue(jsonResponse(driftReport({ missingFeatures: ["v7"] })));
    renderWithSession(<DriftReportDetail />);

    expect(await screen.findByText("Reference PR-AUC")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/drift/reports/1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f");
    expect(screen.getByText("0.840")).toBeInTheDocument();
    expect(screen.getByText("v7")).toBeInTheDocument();
    expect(screen.getByText("3,100")).toBeInTheDocument();
    expect(screen.getByText(/1c9e6f50.html/)).toBeInTheDocument();
  });

  it("says when a report does not exist", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 404, detail: "Drift report x not found" }, 404));
    renderWithSession(<DriftReportDetail />);

    expect(await screen.findByRole("alert")).toHaveTextContent("does not exist");
    expect(screen.getByRole("link", { name: "All drift reports" })).toHaveAttribute("href", "/drift");
  });
});
