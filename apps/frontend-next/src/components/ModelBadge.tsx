interface ModelBadgeProps {
  modelName?: string;
  version: string | null;
}

export function ModelBadge({ modelName = "fraud-xgb", version }: ModelBadgeProps) {
  const known = version !== null && version !== "";
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-2 text-sm"
      title={known ? `${modelName} version ${version} is serving` : "Champion version not loaded"}
    >
      <span aria-hidden className={`size-2 rounded-full ${known ? "bg-safe" : "bg-line"}`} />
      <span className="text-muted">Champion</span>
      <span className="font-medium">{modelName}</span>
      <span className={known ? "font-semibold text-ink" : "text-muted"}>{known ? `v${version}` : "pending"}</span>
    </div>
  );
}
