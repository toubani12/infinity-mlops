import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Drift" };

export default function DriftPage() {
  return (
    <>
      <PageHeader
        title="Drift"
        description="How far recent traffic has moved from the data the champion was trained on."
      />
      <EmptyState
        title="No drift reports yet"
        hint="A report is raised when more than 30% of the features drift, or when PR-AUC on labelled traffic drops by more than 5 points."
      >
        The drift monitor compares each window of predictions with the reference sample. Windows that cross a
        threshold are listed here with the features that moved.
      </EmptyState>
    </>
  );
}
