export interface NavItem {
  href: string;
  label: string;
  hint: string;
}

// Ordered like the self-healing loop: scored traffic, alerts, drift, champion history, then the agent.
export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/transactions", label: "Transactions", hint: "Scored as they arrive" },
  { href: "/alerts", label: "Alerts", hint: "Above the alert threshold" },
  { href: "/drift", label: "Drift", hint: "Live data against reference" },
  { href: "/models", label: "Models", hint: "Champion history" },
  { href: "/agent", label: "Agent", hint: "Retraining and approvals" },
];

export function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}
