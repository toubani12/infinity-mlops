import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeEventSource } from "@/test/FakeEventSource";
import { backoffDelay, useEventStream } from "./useEventStream";

describe("useEventStream", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    FakeEventSource.reset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("doubles the delay up to the cap", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map((n) => backoffDelay(n, 1000, 30_000))).toEqual([
      1000, 2000, 4000, 8000, 16_000, 30_000, 30_000,
    ]);
  });

  it("connects with the token and delivers parsed events", () => {
    const onEvent = vi.fn();
    const { result } = renderHook(() =>
      useEventStream({ path: "/api/stream/alerts", event: "alert", token: "t0k", onEvent }),
    );

    const source = FakeEventSource.latest();
    expect(source.url).toBe("http://api.test/api/stream/alerts?access_token=t0k");
    expect(result.current.status).toBe("connecting");

    act(() => source.open());
    expect(result.current.status).toBe("open");

    act(() => source.emit("alert", { id: "a1", status: "OPEN" }));
    expect(onEvent).toHaveBeenCalledWith({ id: "a1", status: "OPEN" });
  });

  it("reconnects with exponential backoff and resets after a successful open", () => {
    const { result } = renderHook(() =>
      useEventStream({ path: "/s", event: "x", token: "t", onEvent: vi.fn(), baseDelayMs: 1000 }),
    );

    act(() => FakeEventSource.latest().fail());
    expect(FakeEventSource.instances[0].closed).toBe(true);
    expect(result.current).toEqual({ status: "reconnecting", retryInMs: 1000 });

    act(() => vi.advanceTimersByTime(1000));
    expect(FakeEventSource.instances).toHaveLength(2);

    act(() => FakeEventSource.latest().fail());
    expect(result.current.retryInMs).toBe(2000);
    act(() => vi.advanceTimersByTime(1999));
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => vi.advanceTimersByTime(1));
    expect(FakeEventSource.instances).toHaveLength(3);

    act(() => FakeEventSource.latest().open());
    act(() => FakeEventSource.latest().fail());
    expect(result.current.retryInMs).toBe(1000);
  });

  it("stays closed without a token and closes the source on unmount", () => {
    const { result, rerender, unmount } = renderHook(
      ({ token }: { token: string | null }) => useEventStream({ path: "/s", event: "x", token, onEvent: vi.fn() }),
      { initialProps: { token: null as string | null } },
    );
    expect(result.current.status).toBe("closed");
    expect(FakeEventSource.instances).toHaveLength(0);

    rerender({ token: "t" });
    const source = FakeEventSource.latest();
    unmount();

    expect(source.closed).toBe(true);
    act(() => source.fail());
    act(() => vi.advanceTimersByTime(60_000));
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});
