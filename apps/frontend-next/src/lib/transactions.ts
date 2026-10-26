import type { Transaction } from "@/lib/api";

export interface TransactionFilters {
  fraudOnly: boolean;
  minScore: number;
  query: string;
}

export const DEFAULT_FILTERS: TransactionFilters = { fraudOnly: false, minScore: 0, query: "" };

export function matchesFilters(transaction: Transaction, filters: TransactionFilters): boolean {
  if (filters.fraudOnly && transaction.isFraud !== true) {
    return false;
  }
  if (filters.minScore > 0 && (transaction.fraudScore ?? -1) < filters.minScore) {
    return false;
  }
  const query = filters.query.trim().toLowerCase();
  return query === "" || transaction.transactionId.toLowerCase().includes(query);
}

/** Merges a freshly loaded page into the live rows, newest first, without duplicates. */
export function mergeTransactions(latest: Transaction[], rows: Transaction[], limit: number): Transaction[] {
  const ids = new Set(latest.map((row) => row.transactionId));
  return [...latest, ...rows.filter((row) => !ids.has(row.transactionId))]
    .sort((a, b) => Date.parse(b.receivedAt) - Date.parse(a.receivedAt))
    .slice(0, limit);
}

export function upsertTransaction(rows: Transaction[], incoming: Transaction, limit: number): Transaction[] {
  const rest = rows.filter((row) => row.transactionId !== incoming.transactionId);
  return [incoming, ...rest].slice(0, limit);
}
