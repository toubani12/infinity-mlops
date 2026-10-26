import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { isActive } from "./navigation";
import { Sidebar } from "./Sidebar";

const pathname = vi.hoisted(() => ({ current: "/alerts" }));

vi.mock("next/navigation", () => ({ usePathname: () => pathname.current }));

describe("Sidebar", () => {
  it("lists the five sections in loop order", () => {
    render(<Sidebar />);

    expect(screen.getByRole("link", { name: /Transactions/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link").map((link) => link.getAttribute("href"))).toEqual([
      "/transactions",
      "/alerts",
      "/drift",
      "/models",
      "/agent",
    ]);
  });

  it("marks the current section", () => {
    pathname.current = "/drift/1c9e6f50";
    render(<Sidebar />);

    expect(screen.getByRole("link", { current: "page" })).toHaveAttribute("href", "/drift");
  });

  it("matches nested routes only on segment boundaries", () => {
    expect(isActive("/models", "/models")).toBe(true);
    expect(isActive("/models/4", "/models")).toBe(true);
    expect(isActive("/modelsx", "/models")).toBe(false);
  });
});
