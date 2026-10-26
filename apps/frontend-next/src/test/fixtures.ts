import { FEATURE_NAMES, type FeatureVector, type Transaction } from "@/lib/api";
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
