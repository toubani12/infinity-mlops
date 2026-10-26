import type { Alert, AlertStatus } from "@/lib/api";

export type AlertFilter = AlertStatus | "ALL";

const NEXT: Record<AlertStatus, AlertStatus[]> = {
  OPEN: ["ACKNOWLEDGED", "CLOSED"],
  ACKNOWLEDGED: ["CLOSED"],
  CLOSED: [],
};

export function nextStatuses(status: AlertStatus): AlertStatus[] {
  return NEXT[status];
}

export function applyAlertChange(alerts: Alert[], changed: Alert, filter: AlertFilter): Alert[] {
  const matches = filter === "ALL" || changed.status === filter;
  const index = alerts.findIndex((alert) => alert.id === changed.id);
  if (!matches) {
    return index === -1 ? alerts : alerts.filter((alert) => alert.id !== changed.id);
  }
  if (index === -1) {
    return [changed, ...alerts];
  }
  return alerts.map((alert) => (alert.id === changed.id ? changed : alert));
}
