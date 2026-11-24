# Phase 12 — Dhaka Human Ground-Truth Preparation

**Status:** PROTOCOL PREPARED; NO FIELD RECORDS CLAIMED; READINESS BLOCKED
**Date:** 2026-11-25

## 1. Scope

This protocol extends the Phase 11 ground-truth framework
(`backend/app/evidence/ground_truth.py`, `GroundTruthRecord`,
`GroundTruthEvent`). No parallel architecture was created.

Phase 12 **did not** create any live human-verified record, any field
observation, any synthetic-to-operational conversion, or any stakeholder
agreement. The live count of operational verified records remains **0**.

## 2. Evidence classes and their status

| Class | Source type | Automatically ground truth? | Notes |
| --- | --- | --- | --- |
| Citizen report | `CITIZEN_REPORT` | No | Starts `UNVERIFIED`; a report is an observation claim, not verified fact. |
| AI prediction | `AI_PREDICTION` | No | Never ground truth; excluded from verified counts. |
| Human observation | `HUMAN_OBSERVATION` | No | Starts `UNVERIFIED` until independent review. |
| Field observation | `FIELD_OBSERVATION` | No | Must be recorded by a trained observer with time, location, uncertainty and evidence. |
| Resolution evidence | `RESOLUTION_EVIDENCE` | No | Indicates a reported issue was addressed; not proof of the original condition. |
| Independent evidence | `INDEPENDENT_EVIDENCE` | No | Second-party record used in review; independence must be real. |
| Official record | `OFFICIAL_RECORD` | No | Authoritative only if provenance and licence are verified; still reviewed. |

## 3. Verification workflow (existing controls)

1. Records are created with `provenance_kind=OPERATIONAL` and status
   `UNVERIFIED`. `geographic_context_key` is derived from coordinates by the
   central registry; coordinates outside any registered context remain
   `UNKNOWN`.
2. A worker submits for review → `IN_REVIEW`, with an append-only event.
3. A **different** staff reviewer records `VERIFIED`, `REJECTED` or
   `INSUFFICIENT_EVIDENCE`. Creator self-verification is rejected.
4. Every transition appends a `GroundTruthEvent`; history cannot be rewritten.
5. Readiness counts only `OPERATIONAL` + `VERIFIED` records with method,
   evidence and a non-AI source.

Nothing in Phase 12 relaxes these controls.

## 4. Dhaka field evidence protocol

### 4.1 What constitutes a field observation

A direct, first-hand observation of a civic condition by a trained observer
inside the registered `BD-DHAKA` research envelope (or, later, an approved
pilot bbox), recorded at the time and place of observation with:

- observer identity and role (stored as staff/actor reference, not public);
- latitude/longitude in WGS84 with an explicit uncertainty estimate;
- observation timestamp with timezone;
- category, severity and a factual description;
- evidence references (photograph, measurement, official reference);
- `geographic_context_key=BD-DHAKA`;
- provenance and collection method.

A second-hand report, a screenshot without provenance, a model output, or a
nyc-sourced record is **not** a field observation.

### 4.2 What constitutes verification

Verification is a reviewer's recorded judgement that a specific observation
is supported by sufficient, independent, context-consistent evidence. It is
**not** a status change made by the observer, and **not** a mass import.

### 4.3 Acceptable evidence

- Time- and location-stamped observer record with uncertainty.
- Photograph/measurement whose provenance is recorded (no personal data
  beyond what is necessary).
- Official record with a verified source and retrieval metadata.
- Independent second observation by a different trained observer.
- OSM/other public map features may be **context only**, never proof of a
  field condition.

### 4.4 Reviewer independence

- Reviewer must be a different person from the observer/creator.
- Reviewer must not be the submitter of the related citizen report.
- Conflicts of interest are recorded; where independence cannot be
  established, the record stays `IN_REVIEW` or becomes
  `INSUFFICIENT_EVIDENCE`.

### 4.5 Location and time

- Coordinates must be WGS84 and inside the registered context; otherwise the
  record is `UNKNOWN` context and excluded from Dhaka readiness.
- Timezone is mandatory; local Bangladesh time must be converted explicitly.
- Missing time or location → `INSUFFICIENT_EVIDENCE`, never inferred.

### 4.6 Uncertainty and quality

Each observation records positional uncertainty, evidence quality
(high/medium/low) and confidence. Low quality does not become high quality by
reviewer assertion alone; it requires additional evidence.

### 4.7 Duplicate and contradictory evidence

- Duplicate: same observer, condition, location (within stated uncertainty)
  and time window. Duplicates are linked, not double-counted.
- Contradiction: two records asserting incompatible conditions for the same
  place/time. Both are retained with a recorded disagreement; neither is
  silently deleted. Verification requires resolution or explicit abstention.

### 4.8 Rejection and insufficient evidence

- Reject when evidence is fabricated, provenance is unknown/mislabelled,
  location is outside the registered context, or the claim is unsupported.
- `INSUFFICIENT_EVIDENCE` when evidence is plausible but incomplete. This is
  not a negative label and must not be converted into a true negative.

### 4.9 Privacy, consent and safety

- Collect the minimum personal data; avoid faces, license plates and
  identifying details in evidence images unless strictly necessary and
  consented.
- Sensitive records use the existing `sensitive` flag; raw personal data is
  never returned by public APIs.
- Consent is required where a person is identifiable; undocumented consent
  means the evidence is not acceptable.
- Observers do not enter unsafe areas, do not confront individuals, do not
  trespass, and do not perform enforcement or emergency work. Safety overrides
  data collection.
- Bangladesh-specific legal requirements (personal data protection, consent,
  official records, freedom-of-information constraints) are **not** asserted
  here; they require qualified local legal review before any pilot.

### 4.10 Reviewer responsibilities and auditability

Reviewers confirm independence, assess evidence quality, record reasons,
handle disagreement, and abstain when unsure. All actions are append-only
events with actor identity and timestamp. Audit events never expose raw
personal observations publicly.

## 5. Supervised field collection plan (future pilot)

| Element | Plan |
| --- | --- |
| Pilot scope | Small, bounded area inside `BD-DHAKA`; final area is **BLOCKED** pending boundary and stakeholder approval |
| Observation protocol | Sections 4.1–4.6; deterministic daily collection window, paired observations where feasible |
| Reviewer roles | Pilot administrator, data steward, reviewer, field observer, research evaluator, stakeholder representative (categories only; no confirmed persons) |
| Evidence collection | Standard form with location/time/uncertainty/evidence refs; no automated ingestion into verified status |
| Review process | Independent review, disagreement log, abstention allowed, no self-verification |
| Quality checks | Context containment, duplicates, contradictions, provenance completeness, missingness report |
| Data protection | Minimisation, sensitive flag, access restricted to staff roles, retention to be defined by governance |
| Safety | No unsafe field work, no autonomous action, no public claims |
| Documentation | Protocol, event history, manifest of evidence classes, limitation register |
| Evaluation | Counts of verified records by class, inter-reviewer agreement only if independent labels exist; recall remains null without complete reference universes |

## 6. Exit status

- `IMPLEMENTED`: protocol document, geographic tagging on ground-truth
  records, context filtering in workspace and readiness.
- `NOT_ASSESSED`: legal review, reviewer training, field capacity.
- `BLOCKED`: actual field observations, verified operational records, pilot
  collection start.
