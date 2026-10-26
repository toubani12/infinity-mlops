import { apiFetch, type RequestOptions } from "./client";
import type {
  Alert,
  AlertListParams,
  AlertStatus,
  CreateTransactionRequest,
  DevTokenRequest,
  DevTokenResponse,
  DriftReport,
  ModelVersionEvent,
  Page,
  PageParams,
  Transaction,
  TransactionListParams,
  Uuid,
} from "./types";

type CallOptions = Pick<RequestOptions, "token" | "signal">;

export const transactionsApi = {
  list: (params: TransactionListParams = {}, options?: CallOptions) =>
    apiFetch<Page<Transaction>>("/api/transactions", { ...options, query: { ...params } }),
  get: (id: Uuid, options?: CallOptions) =>
    apiFetch<Transaction>(`/api/transactions/${encodeURIComponent(id)}`, options),
  create: (body: CreateTransactionRequest, options?: CallOptions) =>
    apiFetch<Transaction>("/api/transactions", { ...options, method: "POST", body }),
};

export const alertsApi = {
  list: (params: AlertListParams = {}, options?: CallOptions) =>
    apiFetch<Page<Alert>>("/api/alerts", { ...options, query: { ...params } }),
  updateStatus: (id: Uuid, status: AlertStatus, options?: CallOptions) =>
    apiFetch<Alert>(`/api/alerts/${encodeURIComponent(id)}`, { ...options, method: "PATCH", body: { status } }),
};

export const driftApi = {
  reports: (params: PageParams = {}, options?: CallOptions) =>
    apiFetch<Page<DriftReport>>("/api/drift/reports", { ...options, query: { ...params } }),
};

export const modelsApi = {
  versions: (params: PageParams = {}, options?: CallOptions) =>
    apiFetch<Page<ModelVersionEvent>>("/api/models/versions", { ...options, query: { ...params } }),
};

export const authApi = {
  devToken: (body: DevTokenRequest, options?: Pick<RequestOptions, "signal">) =>
    apiFetch<DevTokenResponse>("/api/auth/dev-token", { ...options, method: "POST", body }),
};
