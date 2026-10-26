import type { DriftReport } from "@/lib/api";

export const DRIFT_SHARE_THRESHOLD = 0.3;
export const PR_AUC_DROP_THRESHOLD = 0.05;

export function prAucDelta(report: Pick<DriftReport, "prAuc" | "referencePrAuc">): number | null {
  if (report.prAuc === null || report.referencePrAuc === null) {
    return null;
  }
  return report.prAuc - report.referencePrAuc;
}

export function qualityDropped(report: Pick<DriftReport, "prAuc" | "referencePrAuc">): boolean {
  const delta = prAucDelta(report);
  return delta !== null && -delta > PR_AUC_DROP_THRESHOLD;
}

export function formatPercent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function formatDelta(delta: number): string {
  const points = delta * 100;
  return `${points > 0 ? "+" : points < 0 ? "−" : ""}${Math.abs(points).toFixed(1)} pts`;
}
