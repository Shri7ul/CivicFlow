import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  EmptyState,
  ReadinessScorecard,
  StatusPill,
  formatNumber,
  humanStatus,
} from "./pilot-ui";
import type { ReadinessCategory, ReadinessReport } from "@/types/pilot";

function category(
  key: string,
  status: ReadinessCategory["status"],
  mandatory: boolean,
): ReadinessCategory {
  return {
    key,
    label: humanStatus(key),
    status,
    mandatory,
    owner: "Test owner",
    summary: key + " summary",
    criteria: [
      {
        key: key + ".criterion",
        label: key + " criterion",
        status,
        blocking: mandatory,
        evidence: "Persisted evidence for " + key,
        evidence_refs: ["test"],
      },
    ],
    blocking_issues: status === "FAIL" ? [key + " is blocking"] : [],
  };
}

function report(overrides: Partial<ReadinessReport> = {}): ReadinessReport {
  const categories = [
    category("data_quality", "PASS", true),
    category("freshness", "FAIL", true),
    category("geographic_coverage", "PASS", true),
    category("model_vs_baseline", "FAIL", true),
    category("robustness", "BLOCKED", true),
    category("human_review", "BLOCKED", true),
    category("correlation", "NOT_ASSESSED", true),
    category("infrastructure", "BLOCKED", true),
    category("auditability", "PASS", true),
    category("security", "NOT_ASSESSED", false),
    category("governance", "PASS", true),
    category("operational_constraints", "PASS", true),
    category("reviewer_training", "NOT_ASSESSED", false),
    category("incident_escalation", "NOT_ASSESSED", false),
    category("deployment_rollback", "NOT_ASSESSED", false),
  ];
  return {
    protocol: "phase10-readiness-v1",
    generated_at: "2026-11-24T19:00:00+00:00",
    overall: "NOT_READY",
    ready_for_activation: false,
    activation_blockers: [
      "Model versus baseline (FAIL): 0/4 datasets beat the strongest baseline.",
    ],
    categories,
    counts: {
      PASS: 5,
      FAIL: 2,
      BLOCKED: 3,
      NOT_ASSESSED: 5,
      IN_PROGRESS: 0,
      NOT_APPLICABLE: 0,
      mandatory_total: 11,
      advisory_total: 4,
    },
    mandatory_unmet: ["freshness"],
    advisory_unmet: [],
    pilot_context: null,
    disclaimer:
      "This scorecard never authorizes a pilot or declares a hazard.",
    evidence_policy: "No category is marked PASS without recorded evidence.",
    ...overrides,
  };
}

describe("Phase 10 readiness presentation", () => {
  it("renders a NOT_READY scorecard with evidence and blockers", () => {
    const markup = renderToStaticMarkup(
      <ReadinessScorecard report={report()} />,
    );
    expect(markup).toContain("Not ready");
    expect(markup).toContain("Activation blockers");
    expect(markup).toContain("0/4 datasets beat the strongest baseline.");
    expect(markup).toContain("Freshness");
    expect(markup).toContain("11 mandatory gates");
    expect(markup).toContain("4 advisory categories");
    expect(markup).toContain("Persisted evidence for freshness");
    expect(markup).toContain("never authorizes a pilot");
  });

  it("renders a ready gate result without implying operator authorization", () => {
    const ready = report({
      overall: "READY_FOR_CONTROLLED_PILOT",
      ready_for_activation: true,
      activation_blockers: [],
      categories: report().categories.map((item) => ({
        ...item,
        status: "PASS" as const,
        blocking_issues: [],
      })),
    });
    const markup = renderToStaticMarkup(
      <ReadinessScorecard report={ready} title="Pilot gate" />,
    );
    expect(markup).toContain("Ready for controlled pilot");
    expect(markup).toContain("activation remains a separate administrator action");
    expect(markup).not.toContain("Activation blockers");
  });

  it("keeps empty and status states explicit", () => {
    const markup = renderToStaticMarkup(
      <div>
        <StatusPill status="NEEDS_MORE_DATA" />
        <EmptyState
          title="No review cases"
          hint="Predictions are not verified hazards."
        />
      </div>,
    );
    expect(markup).toContain("Needs more data");
    expect(markup).toContain("No review cases");
    expect(markup).toContain("Predictions are not verified hazards.");
  });

  it("shows unknown metrics as unknown rather than zero", () => {
    expect(formatNumber(null)).toBe("Unknown");
    expect(formatNumber(undefined)).toBe("Unknown");
    expect(formatNumber(0)).toBe("0.000");
  });
});
