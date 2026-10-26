import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  children: ReactNode;
  hint?: ReactNode;
}

export function EmptyState({ title, children, hint }: EmptyStateProps) {
  return (
    <section className="mt-8 rounded-lg border border-dashed border-line bg-surface px-6 py-12 sm:px-10">
      <div className="max-w-xl">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="mt-2 text-[15px] leading-relaxed text-muted">{children}</div>
        {hint ? <div className="mt-5 border-l-2 border-accent pl-4 text-sm leading-relaxed text-ink">{hint}</div> : null}
      </div>
    </section>
  );
}
