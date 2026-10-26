import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
}

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
      <div className="max-w-2xl">
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">{title}</h1>
        <p className="mt-1 text-[15px] text-muted">{description}</p>
      </div>
      {actions}
    </header>
  );
}
