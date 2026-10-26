import { describe, expect, it } from "vitest";
import { agentEvent, agentRun, agentRunDetail } from "@/test/fixtures";
import { applyToDetail, canDecide, formatMetric, formatMetricDelta, metricRows, stepLabel, upsertRun } from "./agent";

describe("agent view logic", () => {
  it("compares challenger and champion with the gate rules", () => {
    const detail = agentRunDetail();
    const rows = metricRows(detail.champion, detail.challenger, detail.gate);

    expect(rows.map((row) => [row.key, row.passes])).toEqual([
      ["prAuc", true],
      ["recallAtP90", true],
      ["p95LatencyMs", true],
    ]);
    expect(rows[0].delta).toBeCloseTo(0.12);
    expect(rows[2].rule).toBe("Under 50 ms");
  });

  it("flags a slower or weaker challenger and handles missing values", () => {
    const rows = metricRows(
      { version: "3", prAuc: 0.8, recallAtP90: null, p95LatencyMs: 6 },
      { version: "4", prAuc: 0.8, recallAtP90: 0.6, p95LatencyMs: 50 },
      { maxP95LatencyMs: 50 },
    );
    expect(rows.map((row) => row.passes)).toEqual([false, true, false]);
    expect(rows[1].delta).toBeNull();

    expect(metricRows(null, null, { maxP95LatencyMs: 50 }).every((row) => row.passes === null)).toBe(true);
  });

  it("formats metrics and signed deltas", () => {
    expect(formatMetric("prAuc", 0.8312)).toBe("0.831");
    expect(formatMetric("p95LatencyMs", 6.44)).toBe("6.4 ms");
    expect(formatMetric("recallAtP90", null)).toBe("Not available");
    expect(formatMetricDelta("prAuc", 0.12)).toBe("+0.120");
    expect(formatMetricDelta("p95LatencyMs", -1.25)).toBe("−1.3 ms");
    expect(formatMetricDelta("prAuc", 0)).toBe("±0.000");
    expect(formatMetricDelta("prAuc", null)).toBe("");
  });

  it("labels steps and decides when a run can be decided", () => {
    expect(stepLabel("retrain_started")).toBe("Retraining started");
    expect(stepLabel("something_new")).toBe("something new");
    expect(canDecide(agentRun())).toBe(true);
    expect(canDecide(agentRun({ status: "RUNNING" }))).toBe(false);
    expect(
      canDecide(
        agentRun({
          pendingCommand: { commandId: "c", action: "approve", actor: "badr", reason: null, sentAt: "2026-10-26T10:08:00Z" },
        }),
      ),
    ).toBe(false);
  });

  it("keeps runs unique and newest first", () => {
    const older = agentRun({ runId: "a", startedAt: "2026-10-25T10:00:00Z" });
    const newer = agentRun({ runId: "b", startedAt: "2026-10-26T10:00:00Z" });

    const runs = upsertRun(upsertRun([], older), newer);
    expect(runs.map((r) => r.runId)).toEqual(["b", "a"]);
    expect(upsertRun(runs, { ...older, status: "PROMOTED" }).map((r) => [r.runId, r.status])).toEqual([
      ["b", "AWAITING_APPROVAL"],
      ["a", "PROMOTED"],
    ]);
  });

  it("merges stream messages into the open run", () => {
    const detail = agentRunDetail({ champion: null, challenger: null, gate: { passed: null, reasons: [], maxP95LatencyMs: 50 } });
    const evaluated = agentEvent(5, "evaluated", {
      payload: {
        champion: { version: "3", pr_auc: 0.7, recall_at_p90: 0.5, p95_latency_ms: 6 },
        challenger: { version: 4, pr_auc: 0.9, recall_at_p90: 0.7, p95_latency_ms: 7 },
        gate: { passed: false, reasons: ["training gate failed"] },
      },
    });
    const run = agentRun({ status: "RUNNING", lastStep: "evaluated" });

    const merged = applyToDetail(detail, { run, event: evaluated });
    expect(merged.events.map((e) => e.seq)).toEqual([1, 2, 3, 4, 5]);
    expect(merged.challenger).toEqual({ version: "4", prAuc: 0.9, recallAtP90: 0.7, p95LatencyMs: 7 });
    expect(merged.gate).toEqual({ passed: false, reasons: ["training gate failed"], maxP95LatencyMs: 50 });
    expect(merged.run.status).toBe("RUNNING");

    expect(applyToDetail(merged, { run, event: evaluated }).events).toHaveLength(5);
    expect(applyToDetail(merged, { run: agentRun({ runId: "other" }), event: null })).toBe(merged);
    expect(applyToDetail(merged, { run: { ...run, status: "PROMOTED" }, event: null }).run.status).toBe("PROMOTED");
  });
});
