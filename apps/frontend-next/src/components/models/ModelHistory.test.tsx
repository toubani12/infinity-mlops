import { screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ModelVersionEvent } from "@/lib/api";
import { jsonResponse, page } from "@/test/fixtures";
import { renderWithSession } from "@/test/renderWithSession";
import { ChampionBadge } from "@/components/ChampionBadge";
import { ModelHistory } from "./ModelHistory";

const promoted: ModelVersionEvent = {
  eventId: "e2",
  timestamp: "2026-10-26T10:11:42Z",
  runId: "5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e",
  modelName: "fraud-xgb",
  version: "4",
  alias: "champion",
  previousVersion: "3",
  reason: "promotion",
};
const rolledBack: ModelVersionEvent = { ...promoted, eventId: "e1", version: "3", previousVersion: "2", reason: "rollback", runId: null };

describe("model history", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists champion moves newest first and marks the serving version", async () => {
    fetchMock.mockResolvedValue(jsonResponse(page([promoted, rolledBack])));
    renderWithSession(<ModelHistory />);

    const headings = await screen.findAllByRole("heading");
    expect(headings.map((h) => h.textContent)).toEqual(["fraud-xgb v4", "fraud-xgb v3"]);
    expect(screen.getByText("Serving now")).toBeInTheDocument();
    expect(screen.getByText("Rollback")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "5b2c7d8e" })).toHaveAttribute(
      "href",
      "/agent/5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e",
    );
    expect(screen.getByText(/Rolled back from v2/)).toBeInTheDocument();
  });

  it("reports load failures", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 500, detail: "boom" }, 500));
    renderWithSession(<ModelHistory />);

    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
  });

  it("feeds the header badge with the latest champion", async () => {
    fetchMock.mockResolvedValue(jsonResponse(page([promoted])));
    renderWithSession(<ChampionBadge />);

    expect(await screen.findByText("v4")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/models/versions?size=1");
  });

  it("keeps the badge pending when signed out", () => {
    renderWithSession(<ChampionBadge />, false);

    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
