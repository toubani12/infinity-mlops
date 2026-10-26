import {
  FEATURE_NAMES,
  type AgentRun,
  type AgentRunDetail,
  type AgentRunEvent,
  type DriftReport,
  type FeatureVector,
  type Transaction,
} from "@/lib/api";
import type { Session } from "@/lib/auth";

export const features = Object.fromEntries(FEATURE_NAMES.map((name, i) => [name, i / 10])) as FeatureVector;

export function transaction(overrides: Partial<Transaction> = {}): Transaction {
  return {
    transactionId: "7f8d4c2e-1b3a-4e5f-9a6b-0c1d2e3f4a5b",
    timestamp: "2026-10-26T09:15:00Z",
    receivedAt: "2026-10-26T09:15:00Z",
    amount: 149.62,
    features,
    label: null,
    fraudScore: 0.0123,
    isFraud: false,
    modelVersion: "3",
    scoredAt: "2026-10-26T09:15:00.041Z",
    ...overrides,
  };
}

export function session(overrides: Partial<Session> = {}): Session {
  return {
    token: "jwt-token",
    expiresAt: new Date(Date.now() + 3_600_000).toISOString(),
    username: "ana",
    role: "analyst",
    ...overrides,
  };
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": status >= 400 ? "application/problem+json" : "application/json" },
  });
}

export function page<T>(content: T[]) {
  return { content, page: 0, size: 100, totalElements: content.length, totalPages: 1 };
}

export function driftReport(overrides: Partial<DriftReport> = {}): DriftReport {
  return {
    reportId: "1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f",
    detectedAt: "2026-10-26T10:00:00Z",
    windowStart: "2026-10-26T09:00:00Z",
    windowEnd: "2026-10-26T10:00:00Z",
    windowRows: 12000,
    driftShare: 0.36,
    driftedFeatures: ["v4", "v10", "v12", "v14", "amount"],
    missingFeatures: [],
    outOfRangeShare: 0,
    prAuc: 0.71,
    referencePrAuc: 0.84,
    recallAtP90: 0.52,
    labeledRows: 3100,
    modelVersion: "3",
    reportUri: "s3://drift-reports/2026/10/26/10/1c9e6f50.html",
    ...overrides,
  };
}

export const RUN_ID = "5b2c7d8e-9f0a-4b1c-8d2e-3f4a5b6c7d8e";

export function agentRun(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    runId: RUN_ID,
    status: "AWAITING_APPROVAL",
    reportId: "1c9e6f50-2d7a-4b8e-8f3c-5a6b7c8d9e0f",
    startedAt: "2026-10-26T10:02:00Z",
    updatedAt: "2026-10-26T10:07:12Z",
    lastStep: "approval_requested",
    lastDecision: "promote",
    lastMessage: "pr_auc 0.830 > champion 0.710",
    championVersion: "3",
    challengerVersion: "4",
    pendingCommand: null,
    decidedBy: null,
    decisionReason: null,
    promotedVersion: null,
    ...overrides,
  };
}

export function agentEvent(seq: number, step: string, overrides: Partial<AgentRunEvent> = {}): AgentRunEvent {
  return {
    eventId: `event-${seq}`,
    runId: RUN_ID,
    seq,
    timestamp: `2026-10-26T10:0${Math.min(seq, 9)}:00Z`,
    step,
    decision: null,
    requiresApproval: step === "approval_requested",
    message: `${step} message`,
    payload: {},
    ...overrides,
  };
}

export function agentRunDetail(overrides: Partial<AgentRunDetail> = {}): AgentRunDetail {
  return {
    run: agentRun(),
    champion: { version: "3", prAuc: 0.71, recallAtP90: 0.52, p95LatencyMs: 6.1 },
    challenger: { version: "4", prAuc: 0.83, recallAtP90: 0.68, p95LatencyMs: 6.4 },
    gate: { passed: true, reasons: ["pr_auc 0.830 > champion 0.710"], maxP95LatencyMs: 50 },
    events: [
      agentEvent(1, "received"),
      agentEvent(2, "qualified", { decision: "real_drift" }),
      agentEvent(3, "evaluated", { decision: "promote" }),
      agentEvent(4, "approval_requested", { decision: "promote" }),
    ],
    ...overrides,
  };
}
