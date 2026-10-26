"use client";

import { useStreamHealth } from "@/hooks/streamHealth";

/** Header summary of every live stream on the page, including the short notice after a resume. */
export function StreamHealthIndicator() {
  const health = useStreamHealth();
  if (health.status === "idle") {
    return null;
  }
  const label =
    health.status === "reconnecting"
      ? `Connection lost, retrying in ${Math.max(1, Math.round((health.retryInMs ?? 0) / 1000))} s`
      : health.status === "connecting"
        ? "Connecting to live data"
        : health.resumed
          ? "Live again, missed updates reloaded"
          : "Live";
  const dot = health.status === "open" ? "bg-safe" : health.status === "reconnecting" ? "bg-caution" : "bg-line";
  return (
    <span
      role="status"
      className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-sm ${
        health.status === "reconnecting" ? "bg-caution-soft text-caution" : "text-muted"
      }`}
    >
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
