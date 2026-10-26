import { Suspense, type ReactNode } from "react";
import { ChampionBadge } from "@/components/ChampionBadge";
import { RequireSession } from "@/components/RequireSession";
import { SessionMenu } from "@/components/SessionMenu";
import { Sidebar, SidebarView } from "@/components/Sidebar";

export default function DashboardLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="md:flex">
      <Suspense fallback={<SidebarView pathname="" />}>
        <Sidebar />
      </Suspense>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center justify-end gap-x-5 gap-y-2 px-4 pt-4 sm:px-8 md:pt-6">
          <SessionMenu />
          <ChampionBadge />
        </div>
        <main className="mx-auto max-w-6xl px-4 pt-4 pb-16 sm:px-8">
          <RequireSession>{children}</RequireSession>
        </main>
      </div>
    </div>
  );
}
