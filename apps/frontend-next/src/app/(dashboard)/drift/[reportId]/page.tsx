import type { Metadata } from "next";
import { Suspense } from "react";
import { DriftReportDetail } from "@/components/drift/DriftReportDetail";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Drift report" };

export default function DriftReportPage() {
  return (
    <>
      <PageHeader
        title="Drift report"
        description="One monitoring window compared with the reference sample, feature by feature."
      />
      <Suspense fallback={<p className="mt-6 text-sm text-muted">Loading the report.</p>}>
        <DriftReportDetail />
      </Suspense>
    </>
  );
}
