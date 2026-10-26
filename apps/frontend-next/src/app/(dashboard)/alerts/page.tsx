import type { Metadata } from "next";
import { AlertsBoard } from "@/components/alerts/AlertsBoard";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Alerts" };

export default function AlertsPage() {
  return (
    <>
      <PageHeader
        title="Alerts"
        description="Transactions that scored at or above the alert threshold and need an analyst."
      />
      <AlertsBoard />
    </>
  );
}
