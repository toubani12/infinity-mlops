import type { Metadata } from "next";
import { Suspense } from "react";
import { AgentRunView } from "@/components/agent/AgentRunView";
import { PageHeader } from "@/components/PageHeader";

export const metadata: Metadata = { title: "Agent run" };

export default function AgentRunPage() {
  return (
    <>
      <PageHeader
        title="Agent run"
        description="Every step of one self-healing run, and the champion against challenger comparison behind it."
      />
      <Suspense fallback={<p className="mt-6 text-sm text-muted">Loading the run.</p>}>
        <AgentRunView />
      </Suspense>
    </>
  );
}
