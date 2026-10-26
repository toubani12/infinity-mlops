import type { Metadata } from "next";
import { ModelHistory } from "@/components/models/ModelHistory";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Models" };

export default function ModelsPage() {
  return (
    <>
      <PageHeader title="Models" description="Which version of fraud-xgb has served traffic, and since when." />
      <ModelHistory />
    </>
  );
}
