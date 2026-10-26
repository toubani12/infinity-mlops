"use client";

import { useState } from "react";
import type { AgentRun } from "@/lib/api";
import { canDecide } from "@/lib/agent";
import { formatWhen } from "@/lib/format";
import { DecisionDialog } from "./DecisionDialog";

interface Props {
  run: AgentRun;
  isAdmin: boolean;
  busy: boolean;
  error: string | null;
  onDecide: (action: "approve" | "reject", reason: string | null) => Promise<boolean>;
}

function Outcome({ run }: { run: AgentRun }) {
  if (run.pendingCommand) {
    const { action, actor, sentAt } = run.pendingCommand;
    return (
      <p className="text-sm">
        {action === "approve" ? "Approval" : "Rejection"} sent by <span className="font-medium">{actor}</span>{" "}
        {formatWhen(sentAt)}. Waiting for the agent to confirm.
      </p>
    );
  }
  if (run.decidedBy) {
    return (
      <p className="text-sm">
        {run.status === "REJECTED" ? "Rejected" : "Approved"} by <span className="font-medium">{run.decidedBy}</span>
        {run.decisionReason ? `: ${run.decisionReason}` : "."}
        {run.promotedVersion ? ` Version ${run.promotedVersion} is now the champion.` : ""}
      </p>
    );
  }
  return null;
}

export function DecisionPanel({ run, isAdmin, busy, error, onDecide }: Props) {
  const [dialog, setDialog] = useState<"approve" | "reject" | null>(null);
  const open = canDecide(run);

  if (!open && !run.pendingCommand && !run.decidedBy) {
    return null;
  }

  async function confirm(reason: string | null) {
    if (dialog && (await onDecide(dialog, reason))) {
      setDialog(null);
    }
  }

  return (
    <section
      aria-label="Decision"
      className={`rounded-lg border p-5 ${open ? "border-caution bg-caution-soft" : "border-line bg-surface"}`}
    >
      <h2 className="font-semibold">{open ? "This promotion waits for a decision" : "Decision"}</h2>
      <div className="mt-2">
        <Outcome run={run} />
      </div>
      {open && isAdmin ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setDialog("approve")}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => setDialog("reject")}
            className="rounded-md border border-risk bg-surface px-3 py-1.5 text-sm font-medium text-risk hover:bg-risk-soft"
          >
            Reject
          </button>
        </div>
      ) : null}
      {open && !isAdmin ? (
        <p className="mt-2 text-sm text-muted">Only an admin can approve or reject a promotion. You can follow it here.</p>
      ) : null}
      {error ? (
        <p role="alert" className="mt-3 rounded-md bg-risk-soft px-3 py-2 text-sm text-risk">
          {error}
        </p>
      ) : null}
      {dialog ? (
        <DecisionDialog
          action={dialog}
          challengerVersion={run.challengerVersion}
          busy={busy}
          onConfirm={confirm}
          onCancel={() => setDialog(null)}
        />
      ) : null}
    </section>
  );
}
