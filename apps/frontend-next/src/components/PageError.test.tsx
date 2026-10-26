import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DashboardError from "@/app/(dashboard)/error";

describe("dashboard error boundary", () => {
  it("shows the failure and retries on demand", async () => {
    const reset = vi.fn();
    render(<DashboardError error={Object.assign(new Error("payload.run is undefined"), { digest: "d1" })} reset={reset} />);

    expect(screen.getByRole("alert")).toHaveTextContent("This page stopped working");
    expect(screen.getByText("payload.run is undefined (d1)")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to transactions" })).toHaveAttribute("href", "/transactions");

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
