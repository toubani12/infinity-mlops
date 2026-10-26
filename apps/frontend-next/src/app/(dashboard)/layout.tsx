import type { ReactNode } from "react";
import { ModelBadge } from "@/components/ModelBadge";
import { Sidebar } from "@/components/Sidebar";

export default function DashboardLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="md:flex">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-end gap-3 px-4 pt-4 sm:px-8 md:pt-6">
          <ModelBadge version={null} />
        </div>
        <main className="mx-auto max-w-6xl px-4 pt-4 pb-16 sm:px-8">{children}</main>
      </div>
    </div>
  );
}
