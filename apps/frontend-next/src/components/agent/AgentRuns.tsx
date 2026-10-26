"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { StreamIndicator } from "@/components/StreamIndicator";
import { useEventStream } from "@/hooks/useEventStream";
import { agentApi, ApiError, type AgentRun, type AgentStreamMessage } from "@/lib/api";
import { stepLabel, upsertRun } from "@/lib/agent";
import { useSession } from "@/lib/auth";
import { formatTime, shortId } from "@/lib/format";
import { RunStatusBadge } from "./RunStatusBadge";

function versions(run: AgentRun): string | null {
  if (!run.challengerVersion) {
    return null;
  }
  return run.championVersion
    ? `Challenger v${run.challengerVersion} against champion v${run.championVersion}`
    : `Challenger v${run.challengerVersion}, no champion yet`;
}

export function AgentRuns() {
  const { session, signOut } = useSession();
  const token = session?.token ?? null;
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    agentApi
      .runs({ size: 50 }, { token, signal: controller.signal })
      .then((page) => {
        setRuns(page.content);
        setError(null);
        setLoaded(true);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (e instanceof ApiError && e.status === 401) {
          signOut("expired");
          return;
        }
        setError(e instanceof Error ? e.message : "Could not load agent runs.");
        setLoaded(true);
      });
    return () => controller.abort();
  }, [token, signOut, reloads]);

  const stream = useEventStream<AgentStreamMessage>({
    path: "/api/stream/agent",
    event: "agent",
    token,
    expiresAt: session?.expiresAt,
    onEvent: (message) => setRuns((current) => upsertRun(current, message.run)),
    onReconnect: () => setReloads((n) => n + 1),
    onUnauthorized: () => signOut("expired"),
  });

  const waiting = runs.filter((run) => run.status === "AWAITING_APPROVAL").length;

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm text-muted">
          {waiting === 0
            ? "No run is waiting for a decision."
            : `${waiting} ${waiting === 1 ? "run waits" : "runs wait"} for an admin decision.`}
        </p>
        <StreamIndicator {...stream} />
      </div>
      {error ? (
        <p role="alert" className="mt-4 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          Could not load agent runs: {error}
        </p>
      ) : null}
      {!loaded ? (
        <p className="mt-6 text-sm text-muted">Loading agent runs.</p>
      ) : runs.length === 0 && !error ? (
        <EmptyState
          title="No agent runs"
          hint="An admin approves or rejects each promotion here. The champion never changes without that decision."
        >
          When drift is confirmed, the agent retrains a challenger and compares it with the champion. Runs appear here
          from the first step.
        </EmptyState>
      ) : (
        <ol className="mt-4 divide-y divide-line rounded-lg border border-line bg-surface">
          {runs.map((run) => (
            <li key={run.runId} className={run.status === "AWAITING_APPROVAL" ? "border-l-2 border-caution" : ""}>
              <Link
                href={`/agent/${run.runId}`}
                className="grid gap-3 px-5 py-4 hover:bg-paper/60 md:grid-cols-[10rem_11rem_1fr] md:items-start"
              >
                <div>
                  <p className="font-medium">{formatTime(run.startedAt)}</p>
                  <p className="font-mono text-[13px] text-muted">{shortId(run.runId)}</p>
                </div>
                <div>
                  <RunStatusBadge status={run.status} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm">
                    <span className="font-medium">{stepLabel(run.lastStep)}</span>
                    <span className="text-muted"> at {formatTime(run.updatedAt)}</span>
                  </p>
                  {run.lastMessage ? <p className="mt-0.5 truncate text-sm text-muted">{run.lastMessage}</p> : null}
                  {versions(run) ? <p className="mt-0.5 text-[13px] text-muted">{versions(run)}</p> : null}
                </div>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
