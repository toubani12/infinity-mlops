import type { Alert, AlertStatus } from "@/lib/api";
import { nextStatuses } from "@/lib/alerts";
import { formatTime, shortId } from "@/lib/format";
import { ScoreBar } from "@/components/ScoreBar";

const STATUS_STYLE: Record<AlertStatus, string> = {
  OPEN: "bg-risk-soft text-risk",
  ACKNOWLEDGED: "bg-caution-soft text-caution",
  CLOSED: "bg-paper text-muted",
};

const STATUS_LABEL: Record<AlertStatus, string> = { OPEN: "Open", ACKNOWLEDGED: "Acknowledged", CLOSED: "Closed" };
const ACTION_LABEL: Record<AlertStatus, string> = { OPEN: "Reopen", ACKNOWLEDGED: "Acknowledge", CLOSED: "Close" };

interface Props {
  alerts: Alert[];
  pendingId: string | null;
  onChangeStatus: (alert: Alert, status: AlertStatus) => void;
}

export function AlertsTable({ alerts, pendingId, onChangeStatus }: Props) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="border-b border-line text-[13px] text-muted">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-medium">Opened</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Transaction</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Fraud score</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Status</th>
            <th scope="col" className="px-4 py-2.5 font-medium">Last change</th>
            <th scope="col" className="px-4 py-2.5 text-right font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {alerts.map((alert) => (
            <tr key={alert.id}>
              <td className="px-4 py-2.5 whitespace-nowrap text-muted">{formatTime(alert.createdAt)}</td>
              <td className="px-4 py-2.5 font-mono text-[13px]" title={alert.transactionId}>
                {shortId(alert.transactionId)}
              </td>
              <td className="px-4 py-2.5">
                <ScoreBar score={alert.fraudScore} />
              </td>
              <td className="px-4 py-2.5">
                <span className={`rounded-full px-2 py-0.5 text-[13px] font-medium ${STATUS_STYLE[alert.status]}`}>
                  {STATUS_LABEL[alert.status]}
                </span>
              </td>
              <td className="px-4 py-2.5 whitespace-nowrap text-muted">{formatTime(alert.updatedAt)}</td>
              <td className="px-4 py-2.5">
                <div className="flex justify-end gap-2">
                  {nextStatuses(alert.status).map((status) => (
                    <button
                      key={status}
                      type="button"
                      disabled={pendingId === alert.id}
                      onClick={() => onChangeStatus(alert, status)}
                      aria-label={`${ACTION_LABEL[status]} alert on ${shortId(alert.transactionId)}`}
                      className={`rounded-md px-2.5 py-1 text-[13px] font-medium disabled:opacity-50 ${
                        status === "CLOSED"
                          ? "border border-line text-ink hover:border-muted"
                          : "bg-accent text-white hover:bg-accent/90"
                      }`}
                    >
                      {ACTION_LABEL[status]}
                    </button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
