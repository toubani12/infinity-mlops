import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Models" };

export default function ModelsPage() {
  return (
    <>
      <PageHeader title="Models" description="Which version of fraud-xgb has served traffic, and since when." />
      <EmptyState title="No promotions recorded">
        Each time the champion changes, through an approved promotion or a rollback, the new and previous versions are
        recorded here.
      </EmptyState>
    </>
  );
}
