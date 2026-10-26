import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Alerts" };

export default function AlertsPage() {
  return (
    <>
      <PageHeader
        title="Alerts"
        description="Transactions that scored at or above the alert threshold and need an analyst."
      />
      <EmptyState
        title="No alerts to review"
        hint="Acknowledge an alert when you start investigating it, and close it once you have reached a decision."
      >
        An alert opens automatically for each transaction whose fraud score reaches the threshold. Nothing has crossed
        it yet.
      </EmptyState>
    </>
  );
}
