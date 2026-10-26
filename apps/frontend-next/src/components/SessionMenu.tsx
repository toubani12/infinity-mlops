"use client";

import { useSession } from "@/lib/auth";

export function SessionMenu() {
  const { session, signOut } = useSession();
  if (!session) {
    return null;
  }
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-muted">
        Signed in as <span className="font-medium text-ink">{session.username}</span> ({session.role})
      </span>
      <button
        type="button"
        onClick={signOut}
        className="rounded-md border border-line bg-surface px-2.5 py-1 font-medium text-ink hover:border-muted"
      >
        Sign out
      </button>
    </div>
  );
}
