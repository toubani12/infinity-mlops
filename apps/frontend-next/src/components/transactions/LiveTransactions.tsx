"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { StreamIndicator } from "@/components/StreamIndicator";
import { useEventStream } from "@/hooks/useEventStream";
import { ApiError, transactionsApi, type Transaction } from "@/lib/api";
import { useSession } from "@/lib/auth";
import {
  DEFAULT_FILTERS,
  matchesFilters,
  mergeTransactions,
  upsertTransaction,
  type TransactionFilters,
} from "@/lib/transactions";
import { TransactionFiltersBar } from "./TransactionFiltersBar";
import { TransactionTable } from "./TransactionTable";

const PAGE_SIZE = 100;
const MAX_ROWS = 300;

export function LiveTransactions() {
  const { session, signOut } = useSession();
  const token = session?.token ?? null;
  const [filters, setFilters] = useState<TransactionFilters>(DEFAULT_FILTERS);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    transactionsApi
      .list({ fraudOnly: filters.fraudOnly || undefined, size: PAGE_SIZE }, { token, signal: controller.signal })
      .then((page) => {
        setRows(page.content);
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
        setError(e instanceof Error ? e.message : "Could not load transactions.");
        setLoaded(true);
      });
    return () => controller.abort();
  }, [token, filters.fraudOnly, signOut]);

  function reloadMissed() {
    if (!token) {
      return;
    }
    transactionsApi
      .list({ fraudOnly: filters.fraudOnly || undefined, size: PAGE_SIZE }, { token })
      .then((page) => setRows((current) => mergeTransactions(page.content, current, MAX_ROWS)))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Could not reload transactions."));
  }

  const stream = useEventStream<Transaction>({
    path: "/api/stream/transactions",
    event: "transaction",
    token,
    expiresAt: session?.expiresAt,
    onEvent: (transaction) => setRows((current) => upsertTransaction(current, transaction, MAX_ROWS)),
    onReconnect: reloadMissed,
    onUnauthorized: () => signOut("expired"),
  });

  const visible = rows.filter((row) => matchesFilters(row, filters));

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <TransactionFiltersBar filters={filters} onChange={setFilters} />
        <StreamIndicator {...stream} />
      </div>
      {error ? (
        <p role="alert" className="mt-4 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          Could not load transactions: {error}
        </p>
      ) : null}
      {!loaded ? (
        <p className="mt-6 text-sm text-muted">Loading transactions.</p>
      ) : visible.length > 0 ? (
        <div className="mt-4">
          <TransactionTable rows={visible} />
          <p className="mt-2 text-[13px] text-muted">
            Showing {visible.length} of the {rows.length} most recent transactions. New scores appear at the top.
          </p>
        </div>
      ) : rows.length > 0 ? (
        <EmptyState title="Nothing matches these filters">
          Lower the minimum score, clear the search or turn off Fraud only to see the {rows.length} loaded
          transactions.
        </EmptyState>
      ) : (
        <EmptyState
          title="No transactions yet"
          hint={
            <>
              Send one with <code className="font-mono text-[13px]">POST /api/transactions</code>, or replay the
              dataset with <code className="font-mono text-[13px]">scripts/seed-transactions.py</code>.
            </>
          }
        >
          Transactions show up here as soon as they are scored, usually within a second of reaching the backend.
        </EmptyState>
      )}
    </section>
  );
}
