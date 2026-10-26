"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useApiResource } from "@/hooks/useApiResource";
import { driftApi } from "@/lib/api";
import { formatDelta, formatPercent, prAucDelta } from "@/lib/drift";
import { formatTime, formatWhen } from "@/lib/format";
import { FeatureChips } from "./FeatureChips";
import { ShareGauge } from "./ShareGauge";

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-6 py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

const metric = (value: number | null, digits = 3) => (value === null ? "Not available" : value.toFixed(digits));

export function DriftReportDetail() {
  const { reportId } = useParams<{ reportId: string }>();
  const report = useApiResource(`drift-report-${reportId}`, (token, signal) =>
    driftApi.report(reportId, { token, signal }),
  );

  const back = (
    <Link href="/drift" className="text-sm font-medium text-accent hover:underline">
      All drift reports
    </Link>
  );

  if (report.state === "loading") {
    return <p className="mt-6 text-sm text-muted">Loading the report.</p>;
  }
  if (report.state === "error") {
    return (
      <div className="mt-6 flex flex-col items-start gap-3">
        <p role="alert" className="rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          {report.status === 404 ? "This drift report does not exist." : `Could not load the report: ${report.message}`}
        </p>
        {back}
      </div>
    );
  }

  const r = report.data;
  const delta = prAucDelta(r);
  return (
    <div className="mt-6 flex flex-col gap-6">
      {back}
      <section className="rounded-lg border border-line bg-surface p-6">
        <h2 className="text-lg font-semibold">
          Window {formatTime(r.windowStart)} to {formatTime(r.windowEnd)}
        </h2>
        <p className="mt-1 text-sm text-muted">
          Detected {formatWhen(r.detectedAt)} over {r.windowRows.toLocaleString("en")} predictions
          {r.modelVersion ? ` from model v${r.modelVersion}` : ""}.
        </p>
        <div className="mt-5">
          <ShareGauge share={r.driftShare} size="lg" />
        </div>
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-lg border border-line bg-surface p-6">
          <h2 className="font-semibold">Features</h2>
          <p className="mt-3 mb-2 text-sm text-muted">Drifted ({r.driftedFeatures.length})</p>
          <FeatureChips features={r.driftedFeatures} />
          <p className="mt-4 mb-2 text-sm text-muted">Missing from live traffic</p>
          <FeatureChips features={r.missingFeatures} tone="missing" />
          <p className="mt-4 text-sm text-muted">
            Out-of-range values:{" "}
            <span className="font-medium text-ink">
              {r.outOfRangeShare === null ? "Not measured" : formatPercent(r.outOfRangeShare)}
            </span>
          </p>
        </section>
        <section className="rounded-lg border border-line bg-surface p-6">
          <h2 className="font-semibold">Model quality on labelled rows</h2>
          <dl className="mt-2 divide-y divide-line text-sm">
            <Metric label="PR-AUC" value={metric(r.prAuc)} />
            <Metric label="Reference PR-AUC" value={metric(r.referencePrAuc)} />
            <Metric label="Change" value={delta === null ? "Not available" : formatDelta(delta)} />
            <Metric label="Recall at 90% precision" value={metric(r.recallAtP90)} />
            <Metric label="Labelled rows" value={r.labeledRows === null ? "None" : r.labeledRows.toLocaleString("en")} />
          </dl>
        </section>
      </div>

      {r.reportUri ? (
        <p className="text-sm text-muted">
          Full Evidently report: <code className="font-mono text-[13px] text-ink">{r.reportUri}</code>
        </p>
      ) : null}
    </div>
  );
}
