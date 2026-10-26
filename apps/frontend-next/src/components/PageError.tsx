"use client";

import Link from "next/link";

interface Props {
  error: Error & { digest?: string };
  onRetry: () => void;
}

/** Shown by the dashboard error boundary: the shell stays usable, only the page body is replaced. */
export function PageError({ error, onRetry }: Props) {
  return (
    <section role="alert" className="mt-8 rounded-lg border border-risk/40 bg-surface px-6 py-10 sm:px-10">
      <h2 className="text-lg font-semibold">This page stopped working</h2>
      <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted">
        Something went wrong while showing this page. Live data keeps flowing in the other sections.
      </p>
      <p className="mt-3 font-mono text-[13px] break-words text-risk">
        {error.message || "Unknown error"}
        {error.digest ? ` (${error.digest})` : ""}
      </p>
      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent/90"
        >
          Try again
        </button>
        <Link href="/transactions" className="rounded-md border border-line px-3 py-1.5 text-sm font-medium">
          Go to transactions
        </Link>
      </div>
    </section>
  );
}
