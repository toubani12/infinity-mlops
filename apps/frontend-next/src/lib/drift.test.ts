import { describe, expect, it } from "vitest";
import { formatDelta, formatPercent, prAucDelta, qualityDropped } from "./drift";

describe("drift helpers", () => {
  it("computes the PR-AUC gap only when both values exist", () => {
    expect(prAucDelta({ prAuc: 0.71, referencePrAuc: 0.84 })).toBeCloseTo(-0.13);
    expect(prAucDelta({ prAuc: null, referencePrAuc: 0.84 })).toBeNull();
  });

  it("flags drops larger than five points", () => {
    expect(qualityDropped({ prAuc: 0.71, referencePrAuc: 0.84 })).toBe(true);
    expect(qualityDropped({ prAuc: 0.81, referencePrAuc: 0.84 })).toBe(false);
    expect(qualityDropped({ prAuc: 0.9, referencePrAuc: 0.84 })).toBe(false);
  });

  it("formats shares and deltas", () => {
    expect(formatPercent(0.364)).toBe("36%");
    expect(formatDelta(-0.13)).toBe("−13.0 pts");
    expect(formatDelta(0.021)).toBe("+2.1 pts");
    expect(formatDelta(0)).toBe("0.0 pts");
  });
});
