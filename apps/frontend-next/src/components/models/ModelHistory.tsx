"use client";

import { EmptyState } from "@/components/EmptyState";
import { useApiResource } from "@/hooks/useApiResource";
import { modelsApi, type ModelVersionEvent } from "@/lib/api";
import { formatWhen, shortId } from "@/lib/format";

function describe(event: ModelVersionEvent): string {
  const from = event.previousVersion ? ` from v${event.previousVersion}` : "";
  return event.reason === "rollback" ? `Rolled back${from}` : `Promoted${from}`;
}

export function ModelHistory() {
  const versions = useApiResource("model-versions", (token, signal) =>
    modelsApi.versions({ size: 50 }, { token, signal }),
  );

  if (versions.state === "loading") {
    return <p className="mt-6 text-sm text-muted">Loading model history.</p>;
  }
  if (versions.state === "error") {
    return (
      <p role="alert" className="mt-6 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
        Could not load model history: {versions.message}
      </p>
    );
  }
  if (versions.data.content.length === 0) {
    return (
      <EmptyState title="No promotions recorded">
        Each time the champion changes, through an approved promotion or a rollback, the new and previous versions are
        recorded here.
      </EmptyState>
    );
  }

  return (
    <ol className="relative mt-8 ml-1.5 border-l border-line">
      {versions.data.content.map((event, index) => {
        const current = index === 0;
        return (
          <li key={event.eventId} className="relative pb-7 pl-7 last:pb-0">
            <span
              aria-hidden
              className={`absolute top-1.5 -left-[6.5px] size-3 rounded-full border-2 ${
                current ? "border-accent bg-accent" : "border-line bg-paper"
              }`}
            />
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className={`text-xl font-semibold ${current ? "text-ink" : "text-muted"}`}>
                {event.modelName} v{event.version}
              </h2>
              {current ? (
                <span className="rounded-full bg-accent-soft px-2 py-0.5 text-[13px] font-medium text-accent">
                  Serving now
                </span>
              ) : null}
              {event.reason === "rollback" ? (
                <span className="rounded-full bg-caution-soft px-2 py-0.5 text-[13px] font-medium text-caution">
                  Rollback
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-sm text-muted">
              {describe(event)} {formatWhen(event.timestamp)}
              {event.runId ? (
                <>
                  , agent run <span className="font-mono text-[13px]">{shortId(event.runId)}</span>
                </>
              ) : null}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
