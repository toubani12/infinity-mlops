import type { EventStreamState } from "@/hooks/useEventStream";

const LABELS = {
  connecting: "Connecting",
  open: "Live",
  closed: "Offline",
} as const;

export function StreamIndicator({ status, retryInMs }: EventStreamState) {
  const label =
    status === "reconnecting"
      ? `Reconnecting in ${Math.max(1, Math.round((retryInMs ?? 0) / 1000))} s`
      : LABELS[status];
  const dot = status === "open" ? "bg-safe" : status === "reconnecting" ? "bg-caution" : "bg-line";
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-muted">
      <span aria-hidden className={`size-2 rounded-full ${dot} ${status === "open" ? "animate-pulse" : ""}`} />
      {label}
    </span>
  );
}
