import type { Metadata } from "next";
import { AgentRuns } from "@/components/agent/AgentRuns";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Agent" };

export default function AgentPage() {
  return (
    <>
      <PageHeader
        title="Agent"
        description="Self-healing runs: what the agent decided, what it retrained, and what waits for your approval."
      />
      <AgentRuns />
    </>
  );
}
