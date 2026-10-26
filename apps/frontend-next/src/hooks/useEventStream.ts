"use client";

import { useEffect, useEffectEvent, useId, useState } from "react";
import { buildUrl } from "@/lib/api";
import { markResumed, reportStream, type StreamStatus } from "./streamHealth";

export type { StreamStatus } from "./streamHealth";

export interface EventStreamOptions<T> {
  path: string;
  event: string;
  token: string | null;
  onEvent: (data: T) => void;
  /** Called when the stream is open again after an error: events sent meanwhile were missed, reload them. */
  onReconnect?: () => void;
  /** Called instead of reconnecting when the token expired or the backend answers 401. */
  onUnauthorized?: () => void;
  expiresAt?: string | null;
  enabled?: boolean;
  baseDelayMs?: number;
  maxDelayMs?: number;
  random?: () => number;
}

export interface EventStreamState {
  status: StreamStatus;
  retryInMs: number | null;
}

/**
 * Equal jitter: half of the exponential delay is fixed, the other half random, so dashboards cut by the same
 * gateway timeout do not all come back at the same instant.
 */
export function backoffDelay(attempt: number, baseDelayMs: number, maxDelayMs: number, random = Math.random): number {
  const cap = Math.min(maxDelayMs, baseDelayMs * 2 ** attempt);
  return Math.round(cap / 2 + (random() * cap) / 2);
}

/** EventSource hides the HTTP status of a failed connection, so a plain request tells a 401 from an outage. */
async function rejectsToken(url: string): Promise<boolean> {
  const controller = new AbortController();
  try {
    const response = await fetch(url, { headers: { Accept: "text/event-stream" }, signal: controller.signal });
    return response.status === 401;
  } catch {
    return false;
  } finally {
    controller.abort();
  }
}

/**
 * EventSource reconnects on its own, but always with the same URL and a fixed delay. Closing it on error and
 * reopening ourselves gives backoff with jitter, picks up a refreshed token and lets the page reload what it missed.
 */
export function useEventStream<T>({
  path,
  event,
  token,
  onEvent,
  onReconnect,
  onUnauthorized,
  expiresAt = null,
  enabled = true,
  baseDelayMs = 1_000,
  maxDelayMs = 30_000,
  random = Math.random,
}: EventStreamOptions<T>): EventStreamState {
  const id = useId();
  const [state, setState] = useState<EventStreamState>({ status: "connecting", retryInMs: null });
  const handleEvent = useEffectEvent((raw: string) => {
    let data: T;
    try {
      data = JSON.parse(raw) as T;
    } catch {
      return;
    }
    onEvent(data);
  });
  const reconnected = useEffectEvent(() => onReconnect?.());
  const unauthorized = useEffectEvent(() => onUnauthorized?.());
  const nextDelay = useEffectEvent((attempt: number) => backoffDelay(attempt, baseDelayMs, maxDelayMs, random));
  const checksToken = onUnauthorized !== undefined;

  useEffect(() => {
    if (!enabled || !token) {
      return;
    }
    const url = buildUrl(path, { access_token: token });
    let attempt = 0;
    let failed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let disposed = false;

    const connect = () => {
      setState({ status: "connecting", retryInMs: null });
      source = new EventSource(url);
      source.onopen = () => {
        attempt = 0;
        setState({ status: "open", retryInMs: null });
        if (failed) {
          failed = false;
          markResumed();
          reconnected();
        }
      };
      source.addEventListener(event, (message) => handleEvent((message as MessageEvent<string>).data));
      source.onerror = () => {
        source?.close();
        if (disposed) {
          return;
        }
        failed = true;
        if (checksToken && expiresAt !== null && Date.parse(expiresAt) <= Date.now()) {
          setState({ status: "closed", retryInMs: null });
          unauthorized();
          return;
        }
        const delay = nextDelay(attempt);
        attempt += 1;
        setState({ status: "reconnecting", retryInMs: delay });
        timer = setTimeout(connect, delay);
        if (checksToken) {
          void rejectsToken(url).then((rejected) => {
            if (rejected && !disposed) {
              clearTimeout(timer);
              setState({ status: "closed", retryInMs: null });
              unauthorized();
            }
          });
        }
      };
    };

    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      source?.close();
    };
  }, [path, event, token, enabled, expiresAt, checksToken]);

  const current: EventStreamState = enabled && token ? state : { status: "closed", retryInMs: null };
  const { status, retryInMs } = current;

  useEffect(() => {
    reportStream(id, { status, retryInMs });
  }, [id, status, retryInMs]);

  useEffect(() => () => reportStream(id, null), [id]);

  return current;
}
