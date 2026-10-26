"use client";

import { useSyncExternalStore } from "react";

export type StreamStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface StreamHealth {
  status: "idle" | "connecting" | "open" | "reconnecting";
  retryInMs: number | null;
  resumed: boolean;
}

export const RESUMED_NOTICE_MS = 5_000;

const IDLE: StreamHealth = { status: "idle", retryInMs: null, resumed: false };
const streams = new Map<string, { status: StreamStatus; retryInMs: number | null }>();
const listeners = new Set<() => void>();
let resumed = false;
let resumedTimer: ReturnType<typeof setTimeout> | undefined;
let snapshot: StreamHealth = IDLE;

function aggregate(): StreamHealth {
  const states = [...streams.values()];
  const reconnecting = states.filter((s) => s.status === "reconnecting");
  if (reconnecting.length > 0) {
    return { status: "reconnecting", retryInMs: Math.min(...reconnecting.map((s) => s.retryInMs ?? 0)), resumed: false };
  }
  if (states.some((s) => s.status === "connecting")) {
    return { status: "connecting", retryInMs: null, resumed };
  }
  return states.some((s) => s.status === "open") ? { status: "open", retryInMs: null, resumed } : IDLE;
}

function publish() {
  snapshot = aggregate();
  listeners.forEach((listener) => listener());
}

/** Called by useEventStream on every state change; null removes the stream when it unmounts. */
export function reportStream(id: string, state: { status: StreamStatus; retryInMs: number | null } | null) {
  if (state === null || state.status === "closed") {
    streams.delete(id);
  } else {
    streams.set(id, state);
  }
  publish();
}

export function markResumed() {
  resumed = true;
  clearTimeout(resumedTimer);
  resumedTimer = setTimeout(() => {
    resumed = false;
    publish();
  }, RESUMED_NOTICE_MS);
  publish();
}

export function resetStreamHealthForTests() {
  streams.clear();
  clearTimeout(resumedTimer);
  resumed = false;
  snapshot = IDLE;
}

export function useStreamHealth(): StreamHealth {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => snapshot,
    () => IDLE,
  );
}
