# Phase 12 — Dhaka Controlled Pilot SOP

**Status:** SOP PREPARED; PILOT NOT APPROVED; ACTIVATION BLOCKED
**Date:** 2026-11-25

## 1. Phase 12 boundary

Phase 12 prepares a **small, supervised, non-autonomous, geographically bounded**
future pilot. It does **not** approve or launch one. No public deployment,
operational action, automated dispatch, public alert, resource allocation or
autonomous civic decision was enabled.

The existing pilot machinery remains authoritative: `Pilot`, `PilotMode`
(`SIMULATION`/`STAGING` only), `PilotTransition` rules, separation of duties
(creator cannot approve; approver cannot activate), and readiness-gated
activation. Phase 12 did not call any activation transition.

## 2. Measurable pilot objectives (to evaluate, not to assert)

| Objective | Measure |
| --- | --- |
| Data quality | Rejected/missing/out-of-context record counts per acquisition |
| Evidence traceability | Share of snapshots with raw+normalized hashes, licence and lineage |
| Geographic coverage | Share of records inside the approved pilot bbox; out-of-scope exclusions recorded |
| Human review | Review cases with independent reviewer and recorded decision |
| Risk ranking usefulness | Reviewer-rated usefulness; not a safety claim |
| Correlation quality | Complete-universe attestation and independent agreement |
| Baseline performance | PR-AUC/R@k against recomputed strongest baseline on Dhaka data |
| Usability | Reviewer task completion and error rate |
| Governance | Separation-of-duties violations (target zero), audit completeness |
| Reviewer workflow | Time per review, abstention and disagreement rates |
| Operational constraints | Zero automated external actions |

## 3. Stakeholder framework — categories only

Potential categories (no institution or individual has agreed to participate):

- city corporation personnel (DNCC/DSCC);
- urban planners (RAJUK / planning academia);
- local community representatives;
- field observers;
- civic engineers;
- researchers;
- reviewers;
- administrators.

No stakeholder agreement, letter of support, or pilot approval is claimed.

## 4. Roles and responsibilities (reuse RBAC)

| Role | Responsibility |
| --- | --- |
| Pilot administrator (`ADMIN`) | Configure pilot record, approve window, own transitions; cannot self-approve or self-activate |
| Data steward (`WORKER`) | Acquire and label context-tagged datasets; preserve provenance; no verification authority |
| Reviewer (`WORKER`, distinct) | Independent review of ground truth, correlation and risk cases; may abstain |
| Field observer (`WORKER`) | Collect supervised field observations with location/time/uncertainty |
| Research evaluator (`WORKER`) | Run pinned, reproducible validation; report nulls honestly |
| Stakeholder representative | Advisory input only; no activation authority |

## 5. SOP phases

1. **Intake.** Only registered, allowlisted, context-tagged sources. Unknown
   provenance remains `UNKNOWN`. No manual URL entry. Records outside the
   registered geography are excluded with a recorded reason.
2. **Evidence review.** Hash/count recomputation, licence and lineage checks,
   quality ledger review. Automated recomputation is not human verification.
3. **Risk review.** Predictions are advisory; a human reviewer records the
   decision. No dispatch or alert is generated.
4. **Escalation.** Only to a human reviewer; no automatic external escalation.
   Safety-critical matters are referred to appropriate authorities by people,
   outside the application.
5. **Incident handling.** CivicFlow records observations and review decisions;
   it does not declare an incident as authoritative fact or verify field
   conditions automatically.
6. **Disagreement.** Logged with both positions; third reviewer or abstention;
   no silent overwrite.
7. **Data quality handling.** Quarantine failed acquisitions; never replace a
   valid snapshot with a failed one; retain rejection reasons.
8. **Privacy.** Minimise personal data; sensitive flag; no public exposure of
   raw observations, reviewer identity or evidence bytes.
9. **Audit.** All transitions append events with actor and timestamp.
10. **Rollback.** Retire `is_current` on a bad snapshot and reinstate the last
    validated snapshot; never delete historical evidence.
11. **Pause.** Administrator may pause intake/review with a recorded reason.
12. **Termination.** At window end or on governance decision; archive the
    evidence manifest and readiness report; no silent continuation.

## 6. Operational restrictions (mandatory during any future pilot)

- No automated dispatch.
- No automatic public alerts.
- No automated resource allocation.
- No autonomous civic decision.
- No authoritative safety claim.
- Human review remains mandatory.
- Predictions remain advisory.
- All actions traceable.
- Pilot activation requires a separate approval action and the existing
  readiness gate.

Phase 12 readiness always returns `pilot_activation_authorized=false`.

## 7. Security and data protection

- Access follows existing RLS/RBAC; no bypass and no new public read path for
  staff evidence.
- The geography endpoints return registry/configuration data only; raw bytes
  and personal observations are never returned.
- Bangladesh legal requirements (personal data protection, consent, records
  management, official data licensing) require qualified legal review; this SOP
  makes no compliance claim.

## 8. Exit status

- `IMPLEMENTED`: SOP, role mapping, restrictions, readiness gating.
- `BLOCKED`: pilot area selection, stakeholder approval, activation.
- `NOT_ASSESSED`: reviewer training, escalation drill, deployment/rollback
  exercise, legal review.
