# Phase 12 — Dhaka Correlation Reference and Labeling Preparation

**Status:** PROTOCOL PREPARED; NO OPERATIONAL LABELS; READINESS BLOCKED
**Date:** 2026-11-25

## 1. Scope

This protocol extends the Phase 11 correlation framework
(`CorrelationUniverse`, `CorrelationCandidate`, `CorrelationReview`,
`backend/app/evidence/universes.py`). No parallel labeling system was created.

Phase 12 created **zero** correlation reference universes and **zero** human
reviewer labels for Dhaka. Recall and F1 from incomplete universes are null,
not estimated.

## 2. Universe model (existing, reused)

`CorrelationUniverse` carries `universe_key`, `version`, `provenance_kind`,
`reference_complete`, `reference_size`, `reference_note`, `candidate_method`,
and — after Phase 12 — `geographic_context_key`. Universes are immutable: an
existing key cannot be overwritten, and `MIXED` provenance is rejected without
a per-candidate ledger. A universe inherits its context from the referenced
validated snapshot; otherwise it remains `UNKNOWN`.

## 3. Dhaka reference-universe workflow

1. **Geographic scope.** Only `BD-DHAKA`-tagged, validated snapshots may be
   used as a reference source. The bbox must be fully contained in the
   registered envelope.
2. **Dataset provenance.** Record source URL, licence, CRS, retrieval time,
   raw/normalized hashes and exclusion reasons for out-of-scope records.
3. **Candidate universe.** Generate candidates deterministically from the
   pinned snapshot using a versioned method; record `candidate_method` and
   its version. No random sampling without a recorded seed.
4. **Temporal matching.** Define an explicit window (e.g. same day / ±N hours)
   before review. The window is part of the method version.
5. **Geographic matching.** Distance threshold and CRS are declared. OSM
   context is not used as the reference truth.
6. **Completeness attestation.** A universe may be `reference_complete=true`
   only when a reviewer attests that all eligible records in the declared
   geography/time window are enumerated, with a written completeness note.
   Otherwise it stays false and recall is null.
7. **Independent reviewers.** At least two reviewers, distinct from candidate
   generation and from each other, label the same candidates. Creation of a
   label by the generator is prohibited by the existing reviewer-separation
   controls.
8. **Disagreement.** Recorded explicitly; no silent majority overwrite.
   Escalate to a third reviewer or abstain.
9. **Abstention.** Allowed and recorded. Abstention is not a negative.
10. **Labeling methodology.** Labels: duplicate / non-duplicate /
    insufficient evidence. Insufficient evidence is never converted to a
    negative.
11. **Review history.** Every review appends an event with actor, timestamp,
    decision and evidence references.
12. **Audit events.** Universe creation, attestation and review actions are
    append-only and staff-only.

## 4. Definitions

- **Duplicate:** two records describing the same civic event within the
  declared spatial and temporal thresholds, supported by evidence.
- **Non-duplicate:** distinct events, or same location but materially
  different times/types with evidence.
- **Insufficient evidence:** plausible but unresolved; excluded from positive
  and negative counts.

## 5. Sampling and bias

- Prefer exhaustive enumeration of the bounded pilot cell/period. If sampling
  is unavoidable, record the sampler, seed, strata and sampling fraction.
- Potential biases to record: reporting bias (who complains), spatial bias
  (denser coverage in mapped areas), temporal bias (day/time), category bias
  (roads over drainage), language/access bias, and OSM mapping-density bias.
- Missing labels are **unknown**, never negatives. Do not fabricate true
  negatives from unlabeled records.

## 6. Metrics and prerequisites

| Metric | Prerequisite |
| --- | --- |
| Precision@k | Reviewed candidates with independent labels |
| Reviewer agreement | Actual independent labels from ≥2 reviewers |
| Recall | Attested `reference_complete=true` universe |
| F1 | Both precision and valid recall |
| Calibration | Sufficient labelled positives/negatives with scores |

Without a complete universe: report precision and agreement only if labels
exist, and report recall/F1 as `null` with reason "reference universe incomplete".

## 7. Exit status

- `IMPLEMENTED`: geographic tagging and context filtering on universes;
  existing immutable-universe and reviewer-separation controls retained.
- `BLOCKED`: no Dhaka reference universe, no candidates, no human labels.
- `NOT_ASSESSED`: inter-reviewer agreement, sampling design, completeness
  attestation capacity.
