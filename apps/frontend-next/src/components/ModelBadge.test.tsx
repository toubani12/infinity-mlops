import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ModelBadge } from "./ModelBadge";
import { EmptyState } from "./EmptyState";

describe("ModelBadge", () => {
  it("shows the serving version", () => {
    render(<ModelBadge version="4" />);

    expect(screen.getByText("v4")).toBeInTheDocument();
    expect(screen.getByTitle("fraud-xgb version 4 is serving")).toBeInTheDocument();
  });

  it("says pending until the version is known", () => {
    render(<ModelBadge version={null} />);

    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByTitle("Champion version not loaded")).toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders the title, explanation and hint", () => {
    render(
      <EmptyState title="No alerts to review" hint="Acknowledge first">
        Nothing crossed the threshold.
      </EmptyState>,
    );

    expect(screen.getByRole("heading", { name: "No alerts to review" })).toBeInTheDocument();
    expect(screen.getByText("Nothing crossed the threshold.")).toBeInTheDocument();
    expect(screen.getByText("Acknowledge first")).toBeInTheDocument();
  });
});
