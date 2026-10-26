import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <>
      <PageHeader
        title="Transactions"
        description="Every transaction the bank sends us, with the fraud score the champion model gave it."
      />
      <EmptyState
        title="No transactions yet"
        hint={
          <>
            Send one with <code className="font-mono text-[13px]">POST /api/transactions</code>, or replay the dataset
            with <code className="font-mono text-[13px]">scripts/seed-transactions.py</code>.
          </>
        }
      >
        Transactions show up here as soon as the backend accepts them. The score, verdict and model version fill in
        once the inference service has scored them, usually within a second.
      </EmptyState>
    </>
  );
}
