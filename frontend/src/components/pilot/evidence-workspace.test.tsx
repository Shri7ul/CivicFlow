import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  EvidenceIntegritySummary,
  EvidenceState,
  ProvenanceBadge,
} from "./evidence-workspace";
import type { EvidenceWorkspace } from "@/types/evidence";

function workspace(overrides: Partial<EvidenceWorkspace> = {}): EvidenceWorkspace {
  return {
    protocol: "phase11-evidence-workspace-v1",
    generated_at: "2026-11-24T21:00:00+00:00",
    evidence_integrity: {
      snapshots: 12,
      current_snapshots: 3,
      quality_counts: { PASS: 10, WARN: 2 },
      provenance_counts: { OPERATIONAL: 12 },
      automated_recomputations: 9,
      quality_issues: [],
      real_data_disclaimer: "Bytes were hashed; physical condition was not inspected.",
    },
    dataset_registry: [],
    snapshots: [],
    ground_truth: {
      total: 7,
      status_counts: { UNVERIFIED: 5, VERIFIED: 2 },
      source_counts: { CITIZEN_REPORT: 7 },
      provenance_counts: { OPERATIONAL: 2, SYNTHETIC: 5 },
      verified_count: 2,
      operational_verified_count: 2,
      human_verification: "PRESENT",
      recent: [],
      workflow: ["Submit for review", "Independent reviewer decides"],
    },
    correlation: {
      universes: [],
      candidate_total: 0,
      reviewed_candidate_total: 0,
      recall_available: false,
      true_negatives_available: false,
      note: "Recall requires a complete universe.",
    },
    infrastructure: {
      domains: [],
      domains_integrated: 1,
      domains_verified: 1,
      sources: [],
      assets_total: 794,
      assets_by_type: { BRIDGE: 794 },
      independent_automated_checks: 4,
      coverage_context: null,
    },
    external_validation: {
      results: [],
      registered_fresh_datasets: 2,
      methodology: "Registered Phase 9 methodology.",
      baseline_note: "Observed holdout PR-AUC only.",
    },
    blockers: ["No operational ground truth is verified."],
    not_assessed: ["Infrastructure-aware model comparison is not assessed."],
    synthetic_separation: "Synthetic fixtures are excluded from operational counts.",
    ...overrides,
  };
}

describe("Phase 11 evidence workspace presentation", () => {
  it("derives summary metrics and blockers from the persisted workspace", () => {
    const markup = renderToStaticMarkup(
      <EvidenceIntegritySummary workspace={workspace()} />,
    );
    expect(markup).toContain("12");
    expect(markup).toContain("3 current");
    expect(markup).toContain("794 active assets");
    expect(markup).toContain("2");
    expect(markup).toContain("No operational ground truth is verified.");
    expect(markup).toContain("Infrastructure-aware model comparison is not assessed.");
    expect(markup).toContain("Evidence blockers (1)");
  });

  it("states an empty blocker list without inventing readiness", () => {
    const markup = renderToStaticMarkup(
      <EvidenceIntegritySummary workspace={workspace({ blockers: [] })} />,
    );
    expect(markup).toContain("Evidence blockers (0)");
    expect(markup).toContain("No blockers are recorded.");
  });

  it("renders loading, error and empty states explicitly", () => {
    const loading = renderToStaticMarkup(<EvidenceState state="loading" />);
    expect(loading).toContain("Loading evidence ledger");
    const error = renderToStaticMarkup(
      <EvidenceState state="error" message="Evidence request failed." />,
    );
    expect(error).toContain("Evidence request failed.");
    const empty = renderToStaticMarkup(<EvidenceState state="empty" />);
    expect(empty).toContain("No evidence workspace");
    expect(empty).toContain("not evidence of readiness");
  });

  it("keeps REAL and SYNTHETIC provenance visually distinct", () => {
    const real = renderToStaticMarkup(<ProvenanceBadge value="REAL" />);
    const synthetic = renderToStaticMarkup(<ProvenanceBadge value="SYNTHETIC" />);
    const unknown = renderToStaticMarkup(<ProvenanceBadge value="UNKNOWN" />);
    expect(real).toContain("REAL");
    expect(real).toContain("emerald");
    expect(synthetic).toContain("SYNTHETIC");
    expect(synthetic).toContain("amber");
    expect(unknown).toContain("UNKNOWN");
    const operational = renderToStaticMarkup(<ProvenanceBadge value="OPERATIONAL" />);
    expect(operational).toContain("OPERATIONAL");
    expect(operational).toContain("cyan");
    expect(operational).not.toContain(">REAL<");
  });
});