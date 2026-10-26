import { formatScore, riskBand } from "@/lib/format";

const BAR = { high: "bg-risk", elevated: "bg-caution", low: "bg-safe" } as const;

export function ScoreBar({ score }: { score: number }) {
  const band = riskBand(score);
  return (
    <span className="flex items-center gap-2.5">
      <span aria-hidden className="h-1.5 w-20 overflow-hidden rounded-full bg-line">
        <span className={`block h-full ${BAR[band]}`} style={{ width: `${Math.round(score * 100)}%` }} />
      </span>
      <span className={band === "high" ? "font-semibold text-risk" : "text-ink"}>{formatScore(score)}</span>
    </span>
  );
}
