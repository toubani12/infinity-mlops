import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider } from "@/lib/auth";
import { resetSessionStoreForTests } from "@/lib/auth/SessionProvider";
import { jsonResponse } from "@/test/fixtures";
import { LoginForm } from "./LoginForm";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

describe("LoginForm", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    resetSessionStoreForTests();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    replace.mockReset();
    window.sessionStorage.clear();
  });

  function renderForm() {
    render(
      <SessionProvider>
        <LoginForm />
      </SessionProvider>,
    );
  }

  it("requests a dev token for the chosen role and opens the dashboard", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ token: "jwt", expiresAt: "2099-01-01T00:00:00Z" }));
    renderForm();

    expect(screen.getByRole("button", { name: "Sign in" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Username"), "badr");
    await userEvent.click(screen.getByLabelText(/admin/i));
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({ username: "badr", role: "admin" });
    expect(replace).toHaveBeenCalledWith("/transactions");
    expect(JSON.parse(window.sessionStorage.getItem("infinity.session") ?? "{}")).toMatchObject({
      token: "jwt",
      username: "badr",
      role: "admin",
    });
  });

  it("explains when the dev endpoint is disabled", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ status: 404, title: "Not Found" }, 404));
    renderForm();

    await userEvent.type(screen.getByLabelText("Username"), "ana");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("local profile");
    expect(replace).not.toHaveBeenCalled();
  });

  it("tells the user when the previous session expired and forgets it after sign in", async () => {
    window.sessionStorage.setItem("infinity.signout", "expired");
    fetchMock.mockResolvedValue(jsonResponse({ token: "jwt", expiresAt: "2099-01-01T00:00:00Z" }));
    renderForm();

    expect(screen.getByRole("status")).toHaveTextContent("Your session expired");
    await userEvent.type(screen.getByLabelText("Username"), "ana");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(window.sessionStorage.getItem("infinity.signout")).toBeNull();
  });
});
