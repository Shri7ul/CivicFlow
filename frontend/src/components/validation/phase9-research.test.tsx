import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Phase9Research } from "./phase9-research";
import type {
  Phase9Report,
  Phase9Summary,
  ResearchDatasetSummary,
} from "@/types/validation";

const noop = () => undefined;

function makeDataset(
  overrides: Partial<ResearchDatasetSummary> = {},
): ResearchDatasetSummary {
  const base: ResearchDatasetSummary = {
    dataset_id: "dataset-1",
    dataset_key: "nyc311-manhattan-2025q2",
    name: "NYC 311 Manhattan Q2",
    region: "Manhattan, New York City",
    period_start: "2025-04-01T00:00:00",
    period_end: "2025-06-30T23:59:59",
    record_count: 4670,
    snapshot_sha256: "b".repeat(64),
    schema_version: "nyc311-v1",
    status: "COMPLETED",
    evidence_kind: "EMPIRICAL_OBSERVATIONAL",
    model_version: "risk-v1",
    config_hash: "config-hash",
    split_method: "rolling_origin",
    role: "external",
    risk: {
      pr_auc: 0.87,
      roc_auc: 0.688,
      precision_at_k: 0.229,
      recall_at_k: 0.44,
      fold_count: 8,
    },
    baselines: [],
    best_baseline: {
      method: "baseline_count",
      pr_auc: 0.928,
      roc_auc: 0.71,
      precision_at_k: 0.3,
      recall_at_k: 0.5,
      fold_count: 8,
      delta_pr_auc: -0.058,
      ci_low: -0.08,
      ci_high: -0.03,
      wins: 1,
      losses: 7,
      sign_test_p: 0.07,
    },
    statistics: {
      method: "percentile_bootstrap",
      config_hash: "config-hash",
      evaluation_unit: "rolling_origin_fold",
      fold_intervals: {
        pr_auc: { n: 8, mean: 0.87, ci_low: 0.83, ci_high: 0.9 },
      },
      paired_pr_auc_vs_baselines: {
        baseline_count: {
          n: 8,
          mean_delta: -0.058,
          ci_low: -0.08,
          ci_high: -0.03,
          wins: 1,
          losses: 7,
          sign_test_p: 0.07,
        },
      },
    },
    density: { classification: "DENSE", mean_label_prevalence: 0.5 },
    sensitivity: {},
    diagnostics: {
      hypotheses: [
        {
          severity: "high",
          finding: "baseline_count outranks the registered model",
          evidence: "mean delta -0.058 across 8 folds",
        },
      ],
      factor_diagnostics: {
        trend: {
          availability_rate: 0.84,
          available_count: 4200,
          observations: 5000,
          zero_share: 0.2,
          mean_normalized: 0.33,
          target_spearman: 0.31,
          mean_when_target_active: 0.4,
          mean_when_target_inactive: 0.2,
        },
      },
      factor_redundancy: [],
      band_distribution: {
      low: { count: 10, share: 0.833 },
      high: { count: 2, share: 0.167 },
    },
      score_distribution: {},
      data_quality: {},
      baseline_comparison: {},
      limitations: [],
    },
    ablation: {
      status: "COMPLETED",
      variants: [
        {
          variant_key: "drop_trend",
          kind: "leave_one_out",
          removed_factors: ["trend"],
          only_factors: [],
          pr_auc: 0.89,
          roc_auc: 0.7,
          precision_at_k: 0.25,
          recall_at_k: 0.45,
          mean_delta: 0.00797,
          ci_low: 0.001712,
          ci_high: 0.015833,
          wins: 6,
          losses: 2,
          sign_test_p: 0.29,
        },
      ],
      ranking: [
        { variant_key: "drop_trend", pr_auc: 0.89, roc_auc: 0.7, precision_at_k: 0.25, recall_at_k: 0.45 },
      ],
      best_variant: "drop_trend",
      best_minus_full_pr_auc: 0.00797,
      interpretation: "Removing trend improves the paired mean.",
      limitations: [],
    },
    candidates: [],
    robustness: {
      status: "COMPLETED",
      base_metrics: {
        pr_auc: 0.87,
        roc_auc: 0.688,
        precision_at_k: 0.229,
        recall_at_k: 0.44,
        fold_count: 8,
      },
      resolution: [
        {
          resolution: 8,
          cell_count: 120,
          pr_auc: 0.87,
          roc_auc: 0.688,
          precision_at_k: 0.229,
          recall_at_k: 0.44,
          mean_spearman: null,
          mean_top20_jaccard: null,
        },
      ],
      target_window: [],
      record_thinning: [],
      density_strata: { note: "Dense cells support the ranking." },
      threshold_sensitivity: {
        origin: "base",
        variants: {
          default: {
            cell_total: 120,
            thresholds: { high: 0.6 },
            cell_counts: { high: 4 },
          },
        },
      },
      missingness: { descriptor_missing_rate: 0.02, borough_missing_rate: 0 },
      limitations: [],
    },
    findings: [],
    limitations: ["Complaint activity is not verified impact."],
    experiments: {},
  };
  return { ...base, ...overrides };
}

const dataset = makeDataset();

const summary: Phase9Summary = {
  protocol_key: "phase9-risk-diagnosis-v1",
  protocol: "Bounded diagnosis protocol",
  split_method: "rolling_origin",
  development_dataset: "nyc311-brooklyn-2025q1",
  dataset_count: 1,
  mean_pr_auc_across_datasets: 0.87,
  evidence_kind: "EMPIRICAL_OBSERVATIONAL",
  evidence_policy: ["Results are empirical observational over complaint snapshots."],
  selection: {
    candidate_key: "drop_trend",
    selection_dataset: "nyc311-brooklyn-2025q1",
    rule: "Highest mean paired PR-AUC delta on the development dataset only.",
    reason: "drop_trend had the highest development mean delta (+0.0063).",
    selection_statistics: {
      n: 8,
      mean_delta: 0.0063,
      ci_low: -0.0012,
      ci_high: 0.0128,
      wins: 5,
      losses: 3,
      sign_test_p: 0.726562,
    },
    removed_factors: ["trend"],
    weights: {},
  },
  datasets: [dataset],
};

const report = {
  protocol_key: "phase9-risk-diagnosis-v1",
  generated_at: "2026-01-01T00:00:00Z",
  source: "persisted_validation_records",
  evidence_kind: "EMPIRICAL_OBSERVATIONAL",
  executive_summary: ["One of three external holdouts improved."],
  phase8_findings: null,
  diagnostic_audit: [],
  datasets: [],
  dataset_quality: [],
  methodology: {},
  split_methodology: {},
  baselines: [],
  ablation: [],
  geographic: [],
  temporal: [],
  sensitivity: [],
  statistics: [],
  model_changes: {
    activated: false,
    activation_state: "NOT_ACTIVATED",
    active_model_version: "risk-v1",
    active_config_hash: "config-hash",
    selection_rule: "Development dataset only.",
    selected_candidate: "drop_trend",
    selection_dataset: "nyc311-brooklyn-2025q1",
    selection_reason: "Highest development mean delta.",
    candidate_rows: [],
    decision:
      "1 of 3 external holdouts showed an interval above zero; evidence is mixed, so the registered model is retained unchanged.",
    governance_note: "Evaluation-only. No model was activated.",
  },
  comparison: [],
  limitations: ["Fold-level intervals describe variability, not deployment confidence."],
  reproducibility: {},
  future_research: ["Collect verified impact labels."],
  dataset_count: 1,
} as unknown as Phase9Report;

describe("Phase9Research", () => {
  it("renders persisted multi-region metrics and the non-activation state", () => {
    const html = renderToStaticMarkup(
      <Phase9Research
        summary={summary}
        report={report}
        loading={false}
        error={null}
        onDownloadReport={noop}
        busy={false}
      />,
    );

    expect(html).toContain("Multi-region and multi-period evaluation");
    expect(html).toContain("External holdout");
    expect(html).toContain("0.870");
    expect(html).toContain("Below best baseline");
    expect(html).toContain("NOT_ACTIVATED");
    expect(html).toContain("drop trend");
    expect(html).toContain("baseline_count outranks the registered model");
  });

  it("shows the report decision text instead of inventing a conclusion", () => {
    const html = renderToStaticMarkup(
      <Phase9Research
        summary={summary}
        report={report}
        loading={false}
        error={null}
        onDownloadReport={noop}
        busy={false}
      />,
    );

    expect(html).toContain("registered model is retained unchanged");
    expect(html).toContain("Evaluation-only. No model was activated.");
  });

  it("lists holdout candidate evaluation with sample labels", () => {
    const candidate = {
      experiment_id: "experiment-9",
      variant_key: "candidate_drop_trend",
      sample: "external_holdout" as const,
      candidate_key: "drop_trend",
      removed_factors: ["trend"],
      metrics: { ...dataset.risk, pr_auc: 0.878, completed_folds: 8 },
      reference_metrics: { ...dataset.risk, pr_auc: 0.87, completed_folds: 8 },
      delta_pr_auc: {
        n: 8,
        mean_delta: 0.00797,
        ci_low: 0.001712,
        ci_high: 0.015833,
        wins: 6,
        losses: 2,
        sign_test_p: 0.29,
      },
      delta_roc_auc: {
        n: 8,
        mean_delta: 0.001,
        ci_low: -0.002,
        ci_high: 0.004,
        wins: 4,
        losses: 4,
        sign_test_p: 0.99,
      },
      activated: false,
      limitations: [],
    };
    const html = renderToStaticMarkup(
      <Phase9Research
        summary={{ ...summary, datasets: [{ ...dataset, candidates: [candidate] }] }}
        report={report}
        loading={false}
        error={null}
        onDownloadReport={noop}
        busy={false}
      />,
    );

    expect(html).toContain("external holdout");
    expect(html).toContain("CI 0.002 to 0.016");
    // Band counts render as numbers, never as a raw object.
    expect(html).toContain("low 10 (83.3%)");
    expect(html).not.toContain("[object Object]");
    expect(html).toContain("0.878000");
  });

  it("renders an honest empty state without placeholder numbers", () => {
    const html = renderToStaticMarkup(
      <Phase9Research
        summary={null}
        report={null}
        loading={false}
        error={null}
        onDownloadReport={noop}
        busy={false}
      />,
    );

    expect(html).toContain("No Phase 9 research is persisted yet.");
    expect(html).toContain("run_phase9_research.py");
    expect(html).not.toContain("Mean PR-AUC");
  });

  it("surfaces a load failure without falling back to fabricated results", () => {
    const html = renderToStaticMarkup(
      <Phase9Research
        summary={null}
        report={null}
        loading={false}
        error="Research endpoint unavailable"
        onDownloadReport={noop}
        busy={false}
      />,
    );

    expect(html).toContain("Research endpoint unavailable");
    expect(html).toContain("No Phase 9 research is persisted yet.");
  });
});