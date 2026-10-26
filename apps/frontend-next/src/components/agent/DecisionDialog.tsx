"use client";

import { useEffect, useId, useState, type FormEvent } from "react";

export const MIN_REASON_LENGTH = 3;

interface Props {
  action: "approve" | "reject";
  challengerVersion: string | null;
  busy: boolean;
  onConfirm: (reason: string | null) => void;
  onCancel: () => void;
}

export function DecisionDialog({ action, challengerVersion, busy, onConfirm, onCancel }: Props) {
  const titleId = useId();
  const [reason, setReason] = useState("");
  const rejecting = action === "reject";
  const valid = !rejecting || reason.trim().length >= MIN_REASON_LENGTH;
  const version = challengerVersion ? `v${challengerVersion}` : "the challenger";

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) {
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (valid && !busy) {
      onConfirm(rejecting ? reason.trim() : null);
    }
  }

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-ink/40 px-4">
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={submit}
        className="w-full max-w-md rounded-lg bg-surface p-6 shadow-lg"
      >
        <h2 id={titleId} className="text-lg font-semibold">
          {rejecting ? `Reject ${version}` : `Promote ${version} to champion`}
        </h2>
        <p className="mt-2 text-sm text-muted">
          {rejecting
            ? "The champion keeps serving. The reason is sent to the agent and stays on the run."
            : "The agent moves the champion alias and the inference service reloads the new version."}
        </p>
        {rejecting ? (
          <label className="mt-4 block text-sm font-medium">
            Reason
            <textarea
              autoFocus
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={500}
              rows={3}
              className="mt-1 block w-full rounded-md border border-line px-3 py-2 font-normal"
            />
            <span className="mt-1 block text-[13px] font-normal text-muted">
              Required, at least {MIN_REASON_LENGTH} characters.
            </span>
          </label>
        ) : null}
        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-line px-3 py-1.5 text-sm font-medium hover:border-muted disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            autoFocus={!rejecting}
            disabled={!valid || busy}
            className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${
              rejecting ? "bg-risk hover:bg-risk/90" : "bg-accent hover:bg-accent/90"
            }`}
          >
            {busy ? "Sending" : rejecting ? "Reject" : "Approve"}
          </button>
        </div>
      </form>
    </div>
  );
}
