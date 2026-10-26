export type Uuid = string;
export type IsoDateTime = string;

export const FEATURE_NAMES = [
  "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10", "v11", "v12", "v13", "v14",
  "v15", "v16", "v17", "v18", "v19", "v20", "v21", "v22", "v23", "v24", "v25", "v26", "v27", "v28",
] as const;

export type FeatureName = (typeof FEATURE_NAMES)[number];
export type FeatureVector = Record<FeatureName, number>;

export interface Page<T> {
  content: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
}

export interface PageParams {
  page?: number;
  size?: number;
}

export interface ProblemDetail {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  errors?: Record<string, string>;
}

export interface Transaction {
  transactionId: Uuid;
  timestamp: IsoDateTime;
  receivedAt: IsoDateTime;
  amount: number;
  features: FeatureVector;
  label: 0 | 1 | null;
  fraudScore: number | null;
  isFraud: boolean | null;
  modelVersion: string | null;
  scoredAt: IsoDateTime | null;
}

export interface CreateTransactionRequest {
  transactionId?: Uuid;
  timestamp?: IsoDateTime;
  amount: number;
  features: FeatureVector;
  label?: 0 | 1;
}

export interface TransactionListParams extends PageParams {
  fraudOnly?: boolean;
}

export const ALERT_STATUSES = ["OPEN", "ACKNOWLEDGED", "CLOSED"] as const;
export type AlertStatus = (typeof ALERT_STATUSES)[number];

export interface Alert {
  id: Uuid;
  transactionId: Uuid;
  fraudScore: number;
  status: AlertStatus;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

export interface AlertListParams extends PageParams {
  status?: AlertStatus;
}

export interface DriftReport {
  reportId: Uuid;
  detectedAt: IsoDateTime;
  windowStart: IsoDateTime;
  windowEnd: IsoDateTime;
  windowRows: number;
  driftShare: number;
  driftedFeatures: string[];
  missingFeatures: string[];
  outOfRangeShare: number | null;
  prAuc: number | null;
  referencePrAuc: number | null;
  recallAtP90: number | null;
  labeledRows: number | null;
  modelVersion: string | null;
  reportUri: string | null;
}

export interface ModelVersionEvent {
  eventId: Uuid;
  timestamp: IsoDateTime;
  runId: Uuid | null;
  modelName: string;
  version: string;
  alias: "champion";
  previousVersion: string | null;
  reason: "promotion" | "rollback" | null;
}

export type Role = "analyst" | "admin";

export interface DevTokenRequest {
  username: string;
  role: Role;
}

export interface DevTokenResponse {
  token: string;
  expiresAt: IsoDateTime;
}

export const AGENT_RUN_STATUSES = [
  "RUNNING", "AWAITING_APPROVAL", "PROMOTED", "REJECTED", "KEPT_CHAMPION", "ESCALATED", "FAILED", "NOISE",
] as const;
export type AgentRunStatus = (typeof AGENT_RUN_STATUSES)[number];

export interface PendingCommand {
  commandId: Uuid;
  action: "approve" | "reject";
  actor: string;
  reason: string | null;
  sentAt: IsoDateTime;
}

export interface AgentRun {
  runId: Uuid;
  status: AgentRunStatus;
  reportId: Uuid | null;
  startedAt: IsoDateTime;
  updatedAt: IsoDateTime;
  lastStep: string;
  lastDecision: string | null;
  lastMessage: string | null;
  championVersion: string | null;
  challengerVersion: string | null;
  pendingCommand: PendingCommand | null;
  decidedBy: string | null;
  decisionReason: string | null;
  promotedVersion: string | null;
}

export interface AgentRunEvent {
  eventId: Uuid;
  runId: Uuid;
  seq: number;
  timestamp: IsoDateTime;
  step: string;
  decision: string | null;
  requiresApproval: boolean;
  message: string | null;
  payload: Record<string, unknown>;
}

export interface ModelMetrics {
  version: string | null;
  prAuc: number | null;
  recallAtP90: number | null;
  p95LatencyMs: number | null;
}

export interface AgentGate {
  passed: boolean | null;
  reasons: string[];
  maxP95LatencyMs: number;
}

export interface AgentRunDetail {
  run: AgentRun;
  champion: ModelMetrics | null;
  challenger: ModelMetrics | null;
  gate: AgentGate;
  events: AgentRunEvent[];
}

/** Payload of the `agent` SSE event: `event` is null when only the run changed (a decision was sent). */
export interface AgentStreamMessage {
  run: AgentRun;
  event: AgentRunEvent | null;
}

export interface AgentRunListParams extends PageParams {
  status?: AgentRunStatus;
}
