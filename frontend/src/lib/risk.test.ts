import { describe, expect, it } from "vitest";

import {
  factorTone,
  formatFactorValue,
  formatRiskConfidence,
  formatRiskDistance,
  formatRiskScore,
  riskCategoryColors,
  riskCategoryLabels,
  trendTone,
} from "@/lib/risk";
import type { RiskFactor, RiskTrend } from "@/types/risk";

const trend: RiskTrend = {
  available: true,
  direction: "INCREASING",
  direction_label: "Increasing",
  delta_score: 12.5,
  current_score: 60,
  previous_score: 47.5,
  current_incident_count: 3,
  previous_incident_count: 2,
  reason: "Current vs previous.",
};

const factor: RiskFactor = {
  key: "severity",
  label: "Incident severity",
  raw_value: 70,
  normalized: 0.7,
  weight: 0.3,
  contribution: 0.21,
  available: true,
  explanation: "Severity explanation.",
};

describe("risk presentation helpers", () => {
  it("formats scores, confidence, and distances without ambiguity", () => {
    expect(formatRiskScore(62.44)).toBe("62.4 / 100");
    expect(formatRiskConfidence(0.726)).toBe("73%");
    expect(formatRiskDistance(420)).toBe("420 m");
    expect(formatRiskDistance(2400)).toBe("2.4 km");
  });

  it("keeps category labels and colors stable", () => {
    expect(riskCategoryLabels.CRITICAL).toBe("Critical");
    expect(riskCategoryColors.CRITICAL).toBe("#fb7185");
    expect(Object.keys(riskCategoryLabels)).toHaveLength(5);
  });

  it("uses trend and factor direction without relying on color alone", () => {
    expect(trendTone(trend)).toContain("rose");
    expect(trendTone({ ...trend, direction: "DECREASING" })).toContain("emerald");
    expect(trendTone({ ...trend, available: false })).toContain("slate");
    expect(factorTone(factor)).toContain("rose");
    expect(factorTone({ ...factor, available: false })).toContain("slate");
    expect(formatFactorValue(factor)).toBe("70%");
  });
});
