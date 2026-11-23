import { describe, expect, it } from "vitest";

import {
  actionStatusTone,
  formatMinutes,
  formatMoney,
  hazardLabels,
  strategyLabels,
} from "@/lib/decisions";

describe("decision helpers", () => {
  it("formats durations and costs", () => {
    expect(formatMinutes(45)).toBe("45 min");
    expect(formatMinutes(150)).toBe("2h 30m");
    expect(formatMoney(1250)).toBe("$1,250");
    expect(formatMoney(null)).toBe("Not estimated");
  });

  it("exposes stable labels and status tones", () => {
    expect(strategyLabels.BALANCED).toBe("Balanced");
    expect(hazardLabels.FLOOD).toBe("Flood");
    expect(actionStatusTone("SCHEDULED")).toContain("emerald");
    expect(actionStatusTone("BLOCKED")).toContain("rose");
  });
});
