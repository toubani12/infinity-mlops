import type { Metadata } from "next";
import { PageHeader } from "@/components/PageHeader";
import { LiveTransactions } from "@/components/transactions/LiveTransactions";

export const metadata: Metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <>
      <PageHeader
        title="Transactions"
        description="Every transaction the bank sends us, with the fraud score the champion model gave it."
      />
      <LiveTransactions />
    </>
  );
}
