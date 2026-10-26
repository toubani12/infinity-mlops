import type { AgentGate, AgentRun, AgentRunDetail, AgentRunStatus, AgentStreamMessage, ModelMetrics } from "@/lib/api";

export type Tone = "accent" | "caution" | "safe" | "risk" | "muted";

export const STATUS_LABEL: Record<AgentRunStatus, string> = {
  RUNNING: "Running",
  AWAITING_APPROVAL: "Awaiting approval",
  PROMOTED: "Promoted",
  REJECTED: "Rejected",
  KEPT_CHAMPION: "Champion kept",
  ESCALATED: "Escalated",
  FAILED: "Failed",
  NOISE: "Noise",
};

export const STATUS_TONE: Record<AgentRunStatus, Tone> = {
  RUNNING: "accent",
  AWAITING_APPROVAL: "caution",
  PROMOTED: "safe",
  REJECTED: "muted",
  KEPT_CHAMPION: "muted",
  ESCALATED: "risk",
  FAILED: "risk",
  NOISE: "muted",
};

export const STEP_LABEL: Record<string, string> = {
  received: "Drift alert received",
  qualified: "Alert qualified",
  escalated: "Escalated to a human",
  retrain_started: "Retraining started",
  retrain_finished: "Retraining finished",
  evaluated: "Challenger evaluated",
  approval_requested: "Approval requested",
  approved: "Approved",
  rejected: "Rejected",
  promoted: "Champion moved",
  rolled_back: "Rolled back",
  failed: "Run failed",
  completed: "Run completed",
};

export function stepLabel(step: string): string {
  return STEP_LABEL[step] ?? step.replaceAll("_", " ");
}

export function canDecide(run: AgentRun): boolean {
  return run.status === "AWAITING_APPROVAL" && run.pendingCommand === null;
}

export type MetricKey = "prAuc" | "recallAtP90" | "p95LatencyMs";

export interface MetricRow {
  key: MetricKey;
  label: string;
  champion: number | null;
  challenger: number | null;
  delta: number | null;
  rule: string;
  /** null while the rule cannot be checked, e.g. no challenger value yet. */
  passes: boolean | null;
}

/** Same rules as the agent gate: beat the champion on PR-AUC and recall, stay under the latency budget. */
export function metricRows(
  champion: ModelMetrics | null,
  challenger: ModelMetrics | null,
  gate: Pick<AgentGate, "maxP95LatencyMs">,
): MetricRow[] {
  const higherIsBetter = (key: "prAuc" | "recallAtP90", label: string): MetricRow => {
    const c = champion?.[key] ?? null;
    const n = challenger?.[key] ?? null;
    return {
      key,
      label,
      champion: c,
      challenger: n,
      delta: c !== null && n !== null ? n - c : null,
      rule: "Above champion",
      passes: n === null ? null : c === null ? true : n > c,
    };
  };
  const c = champion?.p95LatencyMs ?? null;
  const n = challenger?.p95LatencyMs ?? null;
  return [
    higherIsBetter("prAuc", "PR-AUC"),
    higherIsBetter("recallAtP90", "Recall at 90% precision"),
    {
      key: "p95LatencyMs",
      label: "p95 latency",
      champion: c,
      challenger: n,
      delta: c !== null && n !== null ? n - c : null,
      rule: `Under ${gate.maxP95LatencyMs} ms`,
      passes: n === null ? null : n < gate.maxP95LatencyMs,
    },
  ];
}

export function formatMetric(key: MetricKey, value: number | null): string {
  if (value === null) {
    return "Not available";
  }
  return key === "p95LatencyMs" ? `${value.toFixed(1)} ms` : value.toFixed(3);
}

export function formatMetricDelta(key: MetricKey, delta: number | null): string {
  if (delta === null) {
    return "";
  }
  const sign = delta > 0 ? "+" : delta < 0 ? "−" : "±";
  const size = Math.abs(delta);
  return key === "p95LatencyMs" ? `${sign}${size.toFixed(1)} ms` : `${sign}${size.toFixed(3)}`;
}

export function upsertRun(runs: AgentRun[], changed: AgentRun): AgentRun[] {
  const others = runs.filter((run) => run.runId !== changed.runId);
  return [changed, ...others].sort((a, b) => Date.parse(b.startedAt) - Date.parse(a.startedAt));
}

function metricsFromPayload(value: unknown): ModelMetrics | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  const num = (field: string) => (typeof raw[field] === "number" ? (raw[field] as number) : null);
  return {
    version: raw.version == null ? null : String(raw.version),
    prAuc: num("pr_auc"),
    recallAtP90: num("recall_at_p90"),
    p95LatencyMs: num("p95_latency_ms"),
  };
}

function gateFromPayload(value: unknown, current: AgentGate): AgentGate {
  if (typeof value !== "object" || value === null) {
    return current;
  }
  const raw = value as { passed?: unknown; reasons?: unknown };
  return {
    ...current,
    passed: raw.passed === true,
    reasons: Array.isArray(raw.reasons) ? raw.reasons.map(String) : [],
  };
}

/**
 * Applies a stream message to an open run. The metrics travel in the step payload (snake_case, as the agent wrote
 * them), so the comparison table updates without a refetch. A step already shown is not added twice.
 */
export function applyToDetail(detail: AgentRunDetail, message: AgentStreamMessage): AgentRunDetail {
  if (message.run.runId !== detail.run.runId) {
    return detail;
  }
  const event = message.event;
  if (event === null || detail.events.some((e) => e.eventId === event.eventId)) {
    return { ...detail, run: message.run };
  }
  return {
    run: message.run,
    champion: metricsFromPayload(event.payload.champion) ?? detail.champion,
    challenger: metricsFromPayload(event.payload.challenger) ?? detail.challenger,
    gate: gateFromPayload(event.payload.gate, detail.gate),
    events: [...detail.events, event].sort((a, b) => a.seq - b.seq),
  };
}
