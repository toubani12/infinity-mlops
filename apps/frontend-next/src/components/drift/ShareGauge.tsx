import { DRIFT_SHARE_THRESHOLD, formatPercent } from "@/lib/drift";

interface Props {
  share: number;
  threshold?: number;
  size?: "sm" | "lg";
}

export function ShareGauge({ share, threshold = DRIFT_SHARE_THRESHOLD, size = "sm" }: Props) {
  const over = share > threshold;
  return (
    <div className={size === "lg" ? "w-full max-w-md" : "w-36"}>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(share * 100)}
        aria-label="Share of drifted features"
        className={`relative overflow-hidden rounded-full bg-line ${size === "lg" ? "h-3" : "h-1.5"}`}
      >
        <span
          className={`block h-full ${over ? "bg-risk" : "bg-accent"}`}
          style={{ width: `${Math.min(100, Math.round(share * 100))}%` }}
        />
        <span
          aria-hidden
          className="absolute top-0 h-full w-0.5 bg-ink/60"
          style={{ left: `${Math.round(threshold * 100)}%` }}
        />
      </div>
      <p className={`mt-1 ${size === "lg" ? "text-sm" : "text-[13px]"} ${over ? "text-risk" : "text-muted"}`}>
        <span className="font-semibold">{formatPercent(share)}</span> of features drifted, threshold{" "}
        {formatPercent(threshold)}
      </p>
    </div>
  );
}
