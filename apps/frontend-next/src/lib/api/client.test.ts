import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, buildUrl } from "./client";
import { alertsApi, transactionsApi } from "./endpoints";

function jsonResponse(body: unknown, status = 200, type = "application/json") {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": type } });
}

describe("api client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.test/");
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("builds urls from the configured base and drops empty query values", () => {
    expect(buildUrl("/api/transactions", { page: 2, size: 20, fraudOnly: true, status: undefined, q: "" })).toBe(
      "https://api.example.test/api/transactions?page=2&size=20&fraudOnly=true",
    );
  });

  it("falls back to localhost when no base url is configured", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    expect(buildUrl("api/alerts")).toBe("http://localhost:8080/api/alerts");
  });

  it("sends json bodies with the bearer token", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ id: "a1", status: "CLOSED" }));

    const alert = await alertsApi.updateStatus("a1", "CLOSED", { token: "jwt" });

    expect(alert.status).toBe("CLOSED");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.example.test/api/alerts/a1");
    expect(init?.method).toBe("PATCH");
    expect(init?.body).toBe(JSON.stringify({ status: "CLOSED" }));
    expect(init?.headers).toMatchObject({ Authorization: "Bearer jwt", "Content-Type": "application/json" });
  });

  it("passes list filters as query parameters", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ content: [], page: 0, size: 50, totalElements: 0, totalPages: 0 }));

    const page = await transactionsApi.list({ fraudOnly: true, size: 50 });

    expect(page.totalElements).toBe(0);
    expect(fetchMock.mock.calls[0][0]).toBe("https://api.example.test/api/transactions?fraudOnly=true&size=50");
    expect(fetchMock.mock.calls[0][1]?.headers).not.toHaveProperty("Authorization");
  });

  it("raises problem details as ApiError", async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { title: "Bad Request", status: 400, detail: "Invalid request content.", errors: { amount: "must be greater than or equal to 0" } },
        400,
        "application/problem+json",
      ),
    );

    const error = await transactionsApi.get("x").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(400);
    expect((error as ApiError).message).toBe("Invalid request content.");
    expect((error as ApiError).problem?.errors?.amount).toContain("greater");
  });

  it("reports non-json failures with the status code", async () => {
    fetchMock.mockResolvedValue(new Response("gateway timeout", { status: 504 }));

    await expect(apiFetch("/api/alerts")).rejects.toMatchObject({ status: 504, problem: null });
  });

  it("returns undefined for empty responses", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(apiFetch<void>("/api/alerts/1", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
