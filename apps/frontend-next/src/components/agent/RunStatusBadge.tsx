import type { AgentRunStatus } from "@/lib/api";
import { STATUS_LABEL, STATUS_TONE, type Tone } from "@/lib/agent";

const TONE_CLASS: Record<Tone, string> = {
  accent: "bg-accent-soft text-accent",
  caution: "bg-caution-soft text-caution",
  safe: "bg-safe-soft text-safe",
  risk: "bg-risk-soft text-risk",
  muted: "border border-line bg-paper text-muted",
};

export function RunStatusBadge({ status }: { status: AgentRunStatus }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[13px] font-medium whitespace-nowrap ${TONE_CLASS[STATUS_TONE[status]]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
