"use client";

import { useEffect, useEffectEvent, useState } from "react";
import { buildUrl } from "@/lib/api";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface EventStreamOptions<T> {
  path: string;
  event: string;
  token: string | null;
  onEvent: (data: T) => void;
  enabled?: boolean;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

export interface EventStreamState {
  status: StreamStatus;
  retryInMs: number | null;
}

export function backoffDelay(attempt: number, baseDelayMs: number, maxDelayMs: number): number {
  return Math.min(maxDelayMs, baseDelayMs * 2 ** attempt);
}

/**
 * EventSource reconnects on its own, but always with the same URL and a fixed delay. Closing it on error and
 * reopening ourselves gives exponential backoff and picks up a refreshed token.
 */
export function useEventStream<T>({
  path,
  event,
  token,
  onEvent,
  enabled = true,
  baseDelayMs = 1_000,
  maxDelayMs = 30_000,
}: EventStreamOptions<T>): EventStreamState {
  const [state, setState] = useState<EventStreamState>({ status: "connecting", retryInMs: null });
  const handleEvent = useEffectEvent((raw: string) => {
    onEvent(JSON.parse(raw) as T);
  });

  useEffect(() => {
    if (!enabled || !token) {
      return;
    }
    let attempt = 0;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const connect = () => {
      source = new EventSource(buildUrl(path, { access_token: token }));
      source.onopen = () => {
        attempt = 0;
        setState({ status: "open", retryInMs: null });
      };
      source.addEventListener(event, (message) => handleEvent((message as MessageEvent<string>).data));
      source.onerror = () => {
        source?.close();
        if (disposed) {
          return;
        }
        const delay = backoffDelay(attempt, baseDelayMs, maxDelayMs);
        attempt += 1;
        setState({ status: "reconnecting", retryInMs: delay });
        timer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [path, event, token, enabled, baseDelayMs, maxDelayMs]);

  return enabled && token ? state : { status: "closed", retryInMs: null };
}
