import type { DriftReport } from "@/lib/api";
import { formatDelta, prAucDelta, qualityDropped } from "@/lib/drift";

export function QualityDelta({ report }: { report: Pick<DriftReport, "prAuc" | "referencePrAuc"> }) {
  const delta = prAucDelta(report);
  if (delta === null) {
    return <span className="text-sm text-muted">No labels yet</span>;
  }
  return (
    <span className="text-sm">
      <span className="font-semibold">{report.prAuc!.toFixed(2)}</span>
      <span className="text-muted"> against {report.referencePrAuc!.toFixed(2)}</span>
      <span className={`ml-2 ${qualityDropped(report) ? "font-semibold text-risk" : "text-muted"}`}>
        {formatDelta(delta)}
      </span>
    </span>
  );
}
