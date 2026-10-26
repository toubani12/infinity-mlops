import type { Transaction } from "@/lib/api";
import { formatAmount, formatTime, shortId } from "@/lib/format";
import { ScoreBar } from "@/components/ScoreBar";

function Verdict({ transaction }: { transaction: Transaction }) {
  if (transaction.isFraud === null) {
    return <span className="text-muted">Waiting for score</span>;
  }
  return transaction.isFraud ? (
    <span className="rounded-full bg-risk-soft px-2 py-0.5 text-[13px] font-semibold text-risk">Fraud</span>
  ) : (
    <span className="rounded-full bg-safe-soft px-2 py-0.5 text-[13px] font-medium text-safe">Legitimate</span>
  );
}

export function TransactionTable({ rows }: { rows: Transaction[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line text-[13px] text-muted">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">Received</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Transaction</th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">Amount</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Fraud score</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Verdict</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Model</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((t) => (
            <tr key={t.transactionId} className={t.isFraud ? "bg-risk-soft/40" : undefined}>
              <td className="px-4 py-2.5 whitespace-nowrap text-muted">{formatTime(t.receivedAt)}</td>
              <td className="px-4 py-2.5 font-mono text-[13px]" title={t.transactionId}>
                {shortId(t.transactionId)}
              </td>
              <td className="px-4 py-2.5 text-right whitespace-nowrap">{formatAmount(t.amount)}</td>
              <td className="px-4 py-2.5">
                {t.fraudScore === null ? <span className="text-muted">-</span> : <ScoreBar score={t.fraudScore} />}
              </td>
              <td className="px-4 py-2.5 whitespace-nowrap">
                <Verdict transaction={t} />
              </td>
              <td className="px-4 py-2.5 text-muted">{t.modelVersion ? `v${t.modelVersion}` : "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
