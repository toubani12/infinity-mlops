import type { Metadata } from "next";
import { DriftReports } from "@/components/drift/DriftReports";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Drift" };

export default function DriftPage() {
  return (
    <>
      <PageHeader
        title="Drift"
        description="How far recent traffic has moved from the data the champion was trained on."
      />
      <DriftReports />
    </>
  );
}
