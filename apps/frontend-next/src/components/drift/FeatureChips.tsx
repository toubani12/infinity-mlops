interface Props {
  features: string[];
  limit?: number;
  tone?: "drift" | "missing";
}

export function FeatureChips({ features, limit, tone = "drift" }: Props) {
  if (features.length === 0) {
    return <span className="text-sm text-muted">None</span>;
  }
  const shown = limit ? features.slice(0, limit) : features;
  const style = tone === "missing" ? "border-risk/40 text-risk" : "border-line text-ink";
  return (
    <ul className="flex flex-wrap gap-1.5">
      {shown.map((feature) => (
        <li key={feature} className={`rounded border bg-surface px-1.5 py-0.5 font-mono text-[12px] ${style}`}>
          {feature}
        </li>
      ))}
      {features.length > shown.length ? (
        <li className="px-1 py-0.5 text-[12px] text-muted">and {features.length - shown.length} more</li>
      ) : null}
    </ul>
  );
}
