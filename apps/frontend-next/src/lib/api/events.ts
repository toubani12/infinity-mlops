// Kafka payloads from libs/contracts/events (v1). Field names stay snake_case as on the wire.
import type { FeatureVector, IsoDateTime, Uuid } from "./types";

export type TransactionRawEvent = {
  transaction_id: Uuid;
  timestamp: IsoDateTime;
  amount: number;
  label?: 0 | 1 | null;
} & FeatureVector;

export interface TransactionScoredEvent {
  transaction_id: Uuid;
  timestamp: IsoDateTime;
  fraud_score: number;
  is_fraud: boolean;
  threshold?: number;
  model_name?: string;
  model_version: string;
  latency_ms: number;
}

export interface DriftDetectedEvent {
  report_id: Uuid;
  detected_at: IsoDateTime;
  window: { start: IsoDateTime; end: IsoDateTime; rows: number };
  drift_share: number;
  drifted_features: string[];
  missing_features?: string[];
  out_of_range_share?: number;
  metrics: {
    pr_auc?: number | null;
    reference_pr_auc?: number | null;
    recall_at_p90?: number | null;
    labeled_rows?: number;
  };
  model_version?: string;
  report_uri?: string;
}

export interface ModelPromotedEvent {
  event_id: Uuid;
  timestamp: IsoDateTime;
  run_id?: Uuid | null;
  model_name: string;
  version: string;
  alias: "champion";
  previous_version: string | null;
  reason?: "promotion" | "rollback";
}

export type AgentStep =
  | "received" | "qualified" | "escalated" | "retrain_started" | "retrain_finished" | "evaluated"
  | "approval_requested" | "approved" | "rejected" | "promoted" | "rolled_back" | "failed" | "completed";

export type AgentDecision = "noise" | "real_drift" | "data_incident" | "promote" | "keep_champion";

export interface AgentEvent {
  run_id: Uuid;
  event_id: Uuid;
  timestamp: IsoDateTime;
  step: AgentStep;
  decision?: AgentDecision | null;
  requires_approval: boolean;
  message?: string;
  payload: Record<string, unknown>;
}

export interface AgentCommand {
  run_id: Uuid;
  command_id: Uuid;
  timestamp: IsoDateTime;
  action: "approve" | "reject";
  actor: string;
  reason?: string | null;
}
