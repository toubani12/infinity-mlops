import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FakeEventSource } from "@/test/FakeEventSource";
import { resetStreamHealthForTests, useStreamHealth } from "./streamHealth";
import { backoffDelay, useEventStream } from "./useEventStream";

const top = () => 1;

describe("useEventStream", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://api.test");
    FakeEventSource.reset();
    resetStreamHealthForTests();
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    fetchMock.mockReset();
  });

  it("doubles the delay up to the cap", () => {
    expect([0, 1, 2, 3, 4, 5, 6].map((n) => backoffDelay(n, 1000, 30_000, top))).toEqual([
      1000, 2000, 4000, 8000, 16_000, 30_000, 30_000,
    ]);
  });

  it("keeps at least half of the delay and randomizes the rest", () => {
    expect(backoffDelay(3, 1000, 30_000, () => 0)).toBe(4000);
    expect(backoffDelay(3, 1000, 30_000, () => 0.5)).toBe(6000);
    const spread = new Set(Array.from({ length: 20 }, () => backoffDelay(4, 1000, 30_000)));
    expect([...spread].every((delay) => delay >= 8000 && delay <= 16_000)).toBe(true);
    expect(spread.size).toBeGreaterThan(1);
  });

  it("connects with the token and delivers parsed events, skipping malformed ones", () => {
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
    act(() => source.emitRaw("alert", "{not json"));
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ id: "a1", status: "OPEN" });
  });

  it("reconnects with backoff and asks for a reload once open again", () => {
    const onReconnect = vi.fn();
    const { result } = renderHook(() =>
      useEventStream({ path: "/s", event: "x", token: "t", onEvent: vi.fn(), onReconnect, random: top }),
    );
    act(() => FakeEventSource.latest().open());
    expect(onReconnect).not.toHaveBeenCalled();

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
    expect(onReconnect).toHaveBeenCalledTimes(1);
    act(() => FakeEventSource.latest().fail());
    expect(result.current.retryInMs).toBe(1000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stops and reports an expired token instead of reconnecting", () => {
    const onUnauthorized = vi.fn();
    const expiresAt = new Date(Date.now() + 60_000).toISOString();
    const { result } = renderHook(() =>
      useEventStream({ path: "/s", event: "x", token: "t", onEvent: vi.fn(), onUnauthorized, expiresAt }),
    );

    act(() => vi.advanceTimersByTime(61_000));
    act(() => FakeEventSource.latest().fail());

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(result.current.status).toBe("closed");
    act(() => vi.advanceTimersByTime(60_000));
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("checks the status of a failed stream and stops on 401", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 401 }));
    const onUnauthorized = vi.fn();
    renderHook(() => useEventStream({ path: "/s", event: "x", token: "t", onEvent: vi.fn(), onUnauthorized }));

    await act(async () => FakeEventSource.latest().fail());

    expect(String(fetchMock.mock.calls[0][0])).toBe("http://api.test/s?access_token=t");
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    act(() => vi.advanceTimersByTime(60_000));
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("keeps retrying when the backend is only unreachable", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    const onUnauthorized = vi.fn();
    renderHook(() =>
      useEventStream({ path: "/s", event: "x", token: "t", onEvent: vi.fn(), onUnauthorized, random: top }),
    );

    await act(async () => FakeEventSource.latest().fail());
    act(() => vi.advanceTimersByTime(1000));

    expect(onUnauthorized).not.toHaveBeenCalled();
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("feeds the header health with every stream and a resume notice", () => {
    const health = renderHook(() => useStreamHealth());
    const a = renderHook(() => useEventStream({ path: "/a", event: "x", token: "t", onEvent: vi.fn(), random: top }));
    renderHook(() => useEventStream({ path: "/b", event: "x", token: "t", onEvent: vi.fn(), random: top }));
    const [first, second] = FakeEventSource.instances;
    expect(health.result.current.status).toBe("connecting");

    act(() => {
      first.open();
      second.open();
    });
    expect(health.result.current).toEqual({ status: "open", retryInMs: null, resumed: false });

    act(() => second.fail());
    expect(health.result.current).toEqual({ status: "reconnecting", retryInMs: 1000, resumed: false });
    act(() => vi.advanceTimersByTime(1000));
    act(() => FakeEventSource.latest().open());
    expect(health.result.current).toEqual({ status: "open", retryInMs: null, resumed: true });
    act(() => vi.advanceTimersByTime(5000));
    expect(health.result.current.resumed).toBe(false);

    a.unmount();
    expect(health.result.current.status).toBe("open");
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
