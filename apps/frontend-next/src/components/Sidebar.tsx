"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, isActive } from "./navigation";

export function Sidebar() {
  return <SidebarView pathname={usePathname() ?? ""} />;
}

/** Rendered without an active item while the pathname of a dynamic route is not known yet. */
export function SidebarView({ pathname }: { pathname: string }) {
  return (
    <aside className="bg-rail text-rail-text md:sticky md:top-0 md:flex md:h-screen md:w-64 md:flex-col">
      <div className="flex items-baseline gap-2 px-5 pt-5 pb-3 md:pt-7 md:pb-8">
        <span className="text-lg font-semibold tracking-tight text-white">Infinity</span>
        <span className="text-sm text-rail-muted">fraud operations</span>
      </div>

      <nav aria-label="Main" className="overflow-x-auto px-3 pb-3 md:flex-1 md:overflow-visible md:px-5 md:pb-0">
        <ol className="flex gap-1 md:relative md:flex-col md:gap-0 md:before:absolute md:before:top-5 md:before:bottom-5 md:before:left-[5px] md:before:w-px md:before:bg-rail-line md:before:content-['']">
          {NAV_ITEMS.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href} className="md:relative">
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`group flex items-start gap-3 rounded-md px-3 py-2 md:-ml-1 md:px-1 md:py-3 ${
                    active ? "bg-rail-raised md:bg-transparent" : "hover:bg-rail-raised/60 md:hover:bg-transparent"
                  }`}
                >
                  <span
                    aria-hidden
                    className={`relative z-10 mt-1.5 hidden size-[11px] shrink-0 rounded-full border-2 md:block ${
                      active
                        ? "border-accent-soft bg-accent-soft"
                        : "border-rail-line bg-rail group-hover:border-rail-muted"
                    }`}
                  />
                  <span className="flex flex-col">
                    <span className={`whitespace-nowrap text-[15px] ${active ? "font-semibold text-white" : "font-medium"}`}>
                      {item.label}
                    </span>
                    <span className="hidden text-[13px] leading-snug text-rail-muted md:block">{item.hint}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      </nav>

      <p className="hidden px-5 pb-6 text-[13px] leading-snug text-rail-muted md:block">
        Promotions wait for an admin approval before the champion changes.
      </p>
    </aside>
  );
}
