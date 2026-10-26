"use client";

import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { useApiResource } from "@/hooks/useApiResource";
import { driftApi } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { FeatureChips } from "./FeatureChips";
import { QualityDelta } from "./QualityDelta";
import { ShareGauge } from "./ShareGauge";

export function DriftReports() {
  const reports = useApiResource("drift-reports", (token, signal) =>
    driftApi.reports({ size: 50 }, { token, signal }),
  );

  if (reports.state === "loading") {
    return <p className="mt-6 text-sm text-muted">Loading drift reports.</p>;
  }
  if (reports.state === "error") {
    return (
      <p role="alert" className="mt-6 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
        Could not load drift reports: {reports.message}
      </p>
    );
  }
  if (reports.data.content.length === 0) {
    return (
      <EmptyState
        title="No drift reports yet"
        hint="A report is raised when more than 30% of the features drift, or when PR-AUC on labelled traffic drops by more than 5 points."
      >
        The drift monitor compares each window of predictions with the reference sample. Windows that cross a
        threshold are listed here with the features that moved.
      </EmptyState>
    );
  }

  return (
    <ol className="mt-6 divide-y divide-line rounded-lg border border-line bg-surface">
      {reports.data.content.map((report) => (
        <li key={report.reportId}>
          <Link
            href={`/drift/${report.reportId}`}
            className="grid gap-4 px-5 py-4 hover:bg-paper/60 md:grid-cols-[10rem_10rem_1fr_13rem] md:items-start"
          >
            <div>
              <p className="font-medium">{formatTime(report.detectedAt)}</p>
              <p className="text-[13px] text-muted">
                {formatTime(report.windowStart)} to {formatTime(report.windowEnd)}
              </p>
              <p className="text-[13px] text-muted">{report.windowRows.toLocaleString("en")} predictions</p>
            </div>
            <ShareGauge share={report.driftShare} />
            <div>
              <p className="mb-1.5 text-[13px] text-muted">Drifted features</p>
              <FeatureChips features={report.driftedFeatures} limit={8} />
            </div>
            <div>
              <p className="mb-1 text-[13px] text-muted">PR-AUC against reference</p>
              <QualityDelta report={report} />
              {report.modelVersion ? <p className="mt-1 text-[13px] text-muted">Model v{report.modelVersion}</p> : null}
            </div>
          </Link>
        </li>
      ))}
    </ol>
  );
}
