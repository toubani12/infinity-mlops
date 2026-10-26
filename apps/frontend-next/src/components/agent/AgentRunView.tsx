"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { StreamIndicator } from "@/components/StreamIndicator";
import { useEventStream } from "@/hooks/useEventStream";
import { agentApi, ApiError, type AgentRunDetail, type AgentStreamMessage } from "@/lib/api";
import { applyToDetail } from "@/lib/agent";
import { useSession } from "@/lib/auth";
import { formatWhen, shortId } from "@/lib/format";
import { DecisionPanel } from "./DecisionPanel";
import { MetricsComparison } from "./MetricsComparison";
import { RunStatusBadge } from "./RunStatusBadge";
import { RunTimeline } from "./RunTimeline";

type Load =
  | { state: "loading" }
  | { state: "ready"; detail: AgentRunDetail }
  | { state: "error"; status: number | null; message: string };

function updateDetail(load: Load, change: (detail: AgentRunDetail) => AgentRunDetail): Load {
  return load.state === "ready" ? { state: "ready", detail: change(load.detail) } : load;
}

export function AgentRunView() {
  const { runId } = useParams<{ runId: string }>();
  const { session, signOut } = useSession();
  const token = session?.token ?? null;
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [busy, setBusy] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const fetchDetail = useCallback(
    (signal?: AbortSignal) => {
      if (!token) {
        return;
      }
      agentApi
        .run(runId, { token, signal })
        .then((detail) => setLoad({ state: "ready", detail }))
        .catch((e: unknown) => {
          if (signal?.aborted) {
            return;
          }
          if (e instanceof ApiError && e.status === 401) {
            signOut();
            return;
          }
          setLoad({
            state: "error",
            status: e instanceof ApiError ? e.status : null,
            message: e instanceof Error ? e.message : "The request failed.",
          });
        });
    },
    [runId, token, signOut],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchDetail(controller.signal);
    return () => controller.abort();
  }, [fetchDetail]);

  const stream = useEventStream<AgentStreamMessage>({
    path: "/api/stream/agent",
    event: "agent",
    token,
    onEvent: (message) => setLoad((current) => updateDetail(current, (detail) => applyToDetail(detail, message))),
  });

  async function decide(action: "approve" | "reject", reason: string | null): Promise<boolean> {
    if (!token) {
      return false;
    }
    setBusy(true);
    setDecisionError(null);
    try {
      const run =
        action === "approve"
          ? await agentApi.approve(runId, { token })
          : await agentApi.reject(runId, reason ?? "", { token });
      setLoad((current) => updateDetail(current, (detail) => ({ ...detail, run })));
      return true;
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        signOut();
        return false;
      }
      if (e instanceof ApiError && e.status === 409) {
        setDecisionError(`${e.message}. The run was reloaded.`);
        fetchDetail();
        return true;
      }
      setDecisionError(e instanceof Error ? e.message : "The decision could not be sent.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  const back = (
    <Link href="/agent" className="text-sm font-medium text-accent hover:underline">
      All agent runs
    </Link>
  );

  if (load.state === "loading") {
    return <p className="mt-6 text-sm text-muted">Loading the run.</p>;
  }
  if (load.state === "error") {
    return (
      <div className="mt-6 flex flex-col items-start gap-3">
        <p role="alert" className="rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          {load.status === 404 ? "This agent run does not exist." : `Could not load the run: ${load.message}`}
        </p>
        {back}
      </div>
    );
  }

  const { run, champion, challenger, gate, events } = load.detail;
  return (
    <div className="mt-6 flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {back}
        <StreamIndicator {...stream} />
      </div>
      <section className="rounded-lg border border-line bg-surface p-6">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-mono text-lg font-semibold" title={run.runId}>
            Run {shortId(run.runId)}
          </h2>
          <RunStatusBadge status={run.status} />
        </div>
        <p className="mt-1 text-sm text-muted">
          Started {formatWhen(run.startedAt)}
          {run.reportId ? (
            <>
              {" "}from{" "}
              <Link href={`/drift/${run.reportId}`} className="font-medium text-accent hover:underline">
                drift report {shortId(run.reportId)}
              </Link>
            </>
          ) : null}
          .
        </p>
      </section>
      <DecisionPanel
        run={run}
        isAdmin={session?.role === "admin"}
        busy={busy}
        error={decisionError}
        onDecide={decide}
      />
      <section className="rounded-lg border border-line bg-surface p-6">
        <h2 className="mb-4 font-semibold">Champion against challenger</h2>
        <MetricsComparison champion={champion} challenger={challenger} gate={gate} />
      </section>
      <section className="rounded-lg border border-line bg-surface p-6">
        <h2 className="mb-4 font-semibold">Timeline</h2>
        <RunTimeline events={events} />
      </section>
    </div>
  );
}
