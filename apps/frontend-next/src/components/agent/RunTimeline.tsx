import type { AgentRunEvent } from "@/lib/api";
import { stepLabel } from "@/lib/agent";
import { formatTime } from "@/lib/format";

const ATTENTION = new Set(["approval_requested", "failed", "escalated", "rejected"]);

export function RunTimeline({ events }: { events: AgentRunEvent[] }) {
  return (
    <ol className="relative ml-1.5 border-l border-line">
      {events.map((event) => (
        <li key={event.eventId} className="relative pb-5 pl-6 last:pb-0">
          <span
            aria-hidden
            className={`absolute top-1.5 -left-[5.5px] size-2.5 rounded-full ${
              ATTENTION.has(event.step) ? "bg-caution" : "bg-accent"
            }`}
          />
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span className="font-medium">{stepLabel(event.step)}</span>
            <time dateTime={event.timestamp} className="text-[13px] text-muted">
              {formatTime(event.timestamp)}
            </time>
            {event.decision ? (
              <span className="rounded bg-paper px-1.5 font-mono text-[12px] text-muted">{event.decision}</span>
            ) : null}
          </div>
          {event.message ? <p className="mt-0.5 text-sm break-words text-muted">{event.message}</p> : null}
        </li>
      ))}
    </ol>
  );
}
