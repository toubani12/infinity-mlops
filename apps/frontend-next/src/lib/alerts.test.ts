import { describe, expect, it } from "vitest";
import type { Alert } from "@/lib/api";
import { applyAlertChange, nextStatuses } from "./alerts";

const alert = (id: string, status: Alert["status"]): Alert => ({
  id,
  transactionId: `tx-${id}`,
  fraudScore: 0.9,
  status,
  createdAt: "2026-10-26T10:00:00Z",
  updatedAt: "2026-10-26T10:00:00Z",
});

describe("alert changes", () => {
  it("offers forward moves only", () => {
    expect(nextStatuses("OPEN")).toEqual(["ACKNOWLEDGED", "CLOSED"]);
    expect(nextStatuses("ACKNOWLEDGED")).toEqual(["CLOSED"]);
    expect(nextStatuses("CLOSED")).toEqual([]);
  });

  it("prepends new alerts that match the view", () => {
    expect(applyAlertChange([alert("a", "OPEN")], alert("b", "OPEN"), "OPEN").map((a) => a.id)).toEqual(["b", "a"]);
  });

  it("removes alerts that leave the view and replaces them in place otherwise", () => {
    const list = [alert("a", "OPEN"), alert("b", "OPEN")];

    expect(applyAlertChange(list, alert("a", "ACKNOWLEDGED"), "OPEN").map((a) => a.id)).toEqual(["b"]);
    expect(applyAlertChange(list, alert("a", "ACKNOWLEDGED"), "ALL")[0].status).toBe("ACKNOWLEDGED");
    expect(applyAlertChange(list, alert("z", "CLOSED"), "OPEN")).toBe(list);
  });
});
