import type { Metadata } from "next";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Agent" };

export default function AgentPage() {
  return (
    <>
      <PageHeader
        title="Agent"
        description="Self-healing runs: what the agent decided, what it retrained, and what waits for your approval."
      />
      <EmptyState
        title="No agent runs"
        hint="An admin approves or rejects each promotion here. The champion never changes without that decision."
      >
        When drift is confirmed, the agent retrains a challenger and compares it with the champion. Runs appear here
        from the first step.
      </EmptyState>
    </>
  );
}
