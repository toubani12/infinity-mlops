import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { markResumed, reportStream, resetStreamHealthForTests } from "@/hooks/streamHealth";
import { StreamHealthIndicator } from "./StreamHealthIndicator";

describe("StreamHealthIndicator", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetStreamHealthForTests();
  });
  afterEach(() => vi.useRealTimers());

  it("is hidden without live streams and summarizes them otherwise", () => {
    const { container } = render(<StreamHealthIndicator />);
    expect(container).toBeEmptyDOMElement();

    act(() => reportStream("a", { status: "connecting", retryInMs: null }));
    expect(screen.getByRole("status")).toHaveTextContent("Connecting to live data");

    act(() => reportStream("a", { status: "reconnecting", retryInMs: 4200 }));
    expect(screen.getByRole("status")).toHaveTextContent("Connection lost, retrying in 4 s");

    act(() => {
      reportStream("a", { status: "open", retryInMs: null });
      markResumed();
    });
    expect(screen.getByRole("status")).toHaveTextContent("Live again, missed updates reloaded");

    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByRole("status")).toHaveTextContent(/^Live$/);

    act(() => reportStream("a", null));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
