"use client";

import { useEffect, useState } from "react";
import { EmptyState } from "@/components/EmptyState";
import { StreamIndicator } from "@/components/StreamIndicator";
import { useEventStream } from "@/hooks/useEventStream";
import { alertsApi, ApiError, type Alert, type AlertStatus } from "@/lib/api";
import { applyAlertChange, type AlertFilter } from "@/lib/alerts";
import { useSession } from "@/lib/auth";
import { AlertsTable } from "./AlertsTable";

const FILTERS: { value: AlertFilter; label: string }[] = [
  { value: "OPEN", label: "Open" },
  { value: "ACKNOWLEDGED", label: "Acknowledged" },
  { value: "CLOSED", label: "Closed" },
  { value: "ALL", label: "All" },
];

export function AlertsBoard() {
  const { session, signOut } = useSession();
  const token = session?.token ?? null;
  const [filter, setFilter] = useState<AlertFilter>("OPEN");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    alertsApi
      .list({ status: filter === "ALL" ? undefined : filter, size: 100 }, { token, signal: controller.signal })
      .then((page) => {
        setAlerts(page.content);
        setLoaded(true);
      })
      .catch((e: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (e instanceof ApiError && e.status === 401) {
          signOut();
          return;
        }
        setError(e instanceof Error ? e.message : "Could not load alerts.");
        setLoaded(true);
      });
    return () => controller.abort();
  }, [token, filter, signOut]);

  const stream = useEventStream<Alert>({
    path: "/api/stream/alerts",
    event: "alert",
    token,
    onEvent: (alert) => setAlerts((current) => applyAlertChange(current, alert, filter)),
  });

  async function changeStatus(alert: Alert, status: AlertStatus) {
    if (!token) {
      return;
    }
    setPendingId(alert.id);
    setError(null);
    try {
      const updated = await alertsApi.updateStatus(alert.id, status, { token });
      setAlerts((current) => applyAlertChange(current, updated, filter));
    } catch (e) {
      setError(e instanceof Error ? e.message : "The alert could not be updated.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <section className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div role="group" aria-label="Alert status" className="inline-flex rounded-md border border-line bg-surface p-0.5">
          {FILTERS.map((option) => (
            <button
              key={option.value}
              type="button"
              aria-pressed={filter === option.value}
              onClick={() => setFilter(option.value)}
              className={`rounded px-3 py-1.5 text-sm ${
                filter === option.value ? "bg-rail font-medium text-white" : "text-muted hover:text-ink"
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <StreamIndicator {...stream} />
      </div>
      {error ? (
        <p role="alert" className="mt-4 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          {error}
        </p>
      ) : null}
      {!loaded ? (
        <p className="mt-6 text-sm text-muted">Loading alerts.</p>
      ) : alerts.length > 0 ? (
        <div className="mt-4">
          <AlertsTable alerts={alerts} pendingId={pendingId} onChangeStatus={changeStatus} />
        </div>
      ) : (
        <EmptyState
          title={filter === "OPEN" ? "No alerts to review" : "No alerts in this view"}
          hint="Acknowledge an alert when you start investigating it, and close it once you have reached a decision."
        >
          An alert opens automatically for each transaction whose fraud score reaches the threshold. New ones appear
          here without reloading.
        </EmptyState>
      )}
    </section>
  );
}
