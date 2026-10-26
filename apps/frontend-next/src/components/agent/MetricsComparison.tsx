import type { AgentGate, ModelMetrics } from "@/lib/api";
import { formatMetric, formatMetricDelta, metricRows } from "@/lib/agent";

interface Props {
  champion: ModelMetrics | null;
  challenger: ModelMetrics | null;
  gate: AgentGate;
}

export function MetricsComparison({ champion, challenger, gate }: Props) {
  if (!challenger) {
    return (
      <p className="text-sm text-muted">
        The comparison appears once the retrained challenger has been evaluated against the champion.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-line text-[13px] text-muted">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">Metric</th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Champion {champion?.version ? `v${champion.version}` : ""}
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Challenger {challenger.version ? `v${challenger.version}` : ""}
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">Change</th>
            <th scope="col" className="py-2 font-medium">Gate</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {metricRows(champion, challenger, gate).map((row) => (
            <tr key={row.key}>
              <th scope="row" className="py-2.5 pr-4 font-medium">{row.label}</th>
              <td className="py-2.5 pr-4 text-muted">{formatMetric(row.key, row.champion)}</td>
              <td className="py-2.5 pr-4 font-medium">{formatMetric(row.key, row.challenger)}</td>
              <td className="py-2.5 pr-4 font-mono text-[13px]">{formatMetricDelta(row.key, row.delta)}</td>
              <td className="py-2.5">
                <span
                  data-passes={row.passes === null ? "unknown" : String(row.passes)}
                  className={`rounded-full px-2 py-0.5 text-[13px] font-medium whitespace-nowrap ${
                    row.passes === null
                      ? "bg-paper text-muted"
                      : row.passes
                        ? "bg-safe-soft text-safe"
                        : "bg-risk-soft text-risk"
                  }`}
                >
                  {row.rule}
                  {row.passes === null ? "" : row.passes ? ", met" : ", missed"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {gate.reasons.length > 0 ? (
        <div className="mt-4 text-sm">
          <p className={gate.passed ? "font-medium text-safe" : "font-medium text-risk"}>
            {gate.passed ? "The agent's gate passed" : "The agent's gate failed"}
          </p>
          <ul className="mt-1 list-disc pl-5 text-muted">
            {gate.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
