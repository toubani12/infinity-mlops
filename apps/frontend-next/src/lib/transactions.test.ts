import { describe, expect, it } from "vitest";
import { transaction } from "@/test/fixtures";
import { formatAmount, formatTime, riskBand, shortId } from "./format";
import { DEFAULT_FILTERS, matchesFilters, upsertTransaction } from "./transactions";

describe("transaction filters", () => {
  const fraud = transaction({ transactionId: "aaaa1111-0000", fraudScore: 0.91, isFraud: true });
  const legit = transaction({ transactionId: "bbbb2222-0000", fraudScore: 0.12, isFraud: false });
  const pending = transaction({ transactionId: "cccc3333-0000", fraudScore: null, isFraud: null, modelVersion: null });

  it("keeps everything by default", () => {
    expect([fraud, legit, pending].filter((t) => matchesFilters(t, DEFAULT_FILTERS))).toHaveLength(3);
  });

  it("applies fraud only, minimum score and id search together", () => {
    expect(matchesFilters(legit, { ...DEFAULT_FILTERS, fraudOnly: true })).toBe(false);
    expect(matchesFilters(pending, { ...DEFAULT_FILTERS, minScore: 0.1 })).toBe(false);
    expect(matchesFilters(legit, { ...DEFAULT_FILTERS, minScore: 0.1 })).toBe(true);
    expect(matchesFilters(fraud, { ...DEFAULT_FILTERS, query: " AAAA11 " })).toBe(true);
    expect(matchesFilters(legit, { ...DEFAULT_FILTERS, query: "aaaa" })).toBe(false);
  });

  it("moves updated rows to the top and caps the list", () => {
    const rescored = { ...legit, fraudScore: 0.7 };

    expect(upsertTransaction([fraud, legit], rescored, 10)).toEqual([rescored, fraud]);
    expect(upsertTransaction([fraud, legit], pending, 2)).toEqual([pending, fraud]);
  });
});

describe("format", () => {
  it("formats amounts, ids, times and risk bands", () => {
    expect(formatAmount(149.62)).toBe("€149.62");
    expect(shortId("7f8d4c2e-1b3a-4e5f")).toBe("7f8d4c2e");
    expect(formatTime("2026-10-26T09:15:07Z", new Date("2026-10-26T12:00:00Z"))).toMatch(/\d{2}:15:07/);
    expect(formatTime("2026-10-20T09:15:07Z", new Date("2026-10-26T12:00:00Z"))).toMatch(/20 Oct/);
    expect([riskBand(0.9), riskBand(0.3), riskBand(0.1)]).toEqual(["high", "elevated", "low"]);
  });
});
