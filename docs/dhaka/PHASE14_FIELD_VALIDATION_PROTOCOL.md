# Phase 14 — Field Observation and Validation Protocol

Status: **WORKFLOW IMPLEMENTED / NO OPERATIONAL FIELD RECORDS**

## 1. Entity and states

`FieldObservation` (`backend/app/models/phase14.py`, migration `0024`) is a new
human-observation entity, separate from `GroundTruthRecord`.

| State | Meaning |
| --- | --- |
| DRAFT | Created by a staff observer; not submitted |
| SUBMITTED | Evidence reference or hash present; awaiting reviewer assignment |
| PENDING_REVIEW | Reviewer assigned; awaiting an explicit decision |
| VERIFIED | Independent reviewer accepted the observation with evidence |
| REJECTED | Independent reviewer rejected it, with a recorded reason |
| REQUIRES_REVISION | Reviewer requested specific changes; revision counter incremented |

`DUPLICATE` is a rejection decision with an explicit `duplicate_of_id` link.
No state is entered by a model prediction or by a client-supplied status.

## 2. Required fields

Observer identity and role snapshot (server-owned), observation timestamp, WGS84
location, category, description, evidence references, evidence SHA-256,
provenance kind (`OPERATIONAL` at creation), confidence (0..1), status, revision
counter, reviewer, review timestamp, decision, rejection reason, revision notes,
duplicate link and ground-truth link.

The geographic context is resolved server-side from the point. A point outside
all registered contexts is rejected. A NYC point resolves to `US-NYC`, never to
`BD-DHAKA`.

## 3. Review rules

- Only staff (WORKER/ADMIN) can create observations; the server sets the observer.
- Only the observer or an admin can submit; evidence is required.
- Only an admin can assign a reviewer; the reviewer must be active staff and
  distinct from the observer.
- Only the assigned reviewer or an admin can decide; the observer can never
  verify their own observation.
- `VERIFIED` requires evidence references or an evidence hash.
- `REJECTED` requires a reason of at least 10 characters.
- `REQUIRES_REVISION` requires revision notes of at least 10 characters.
- Every transition appends a `FieldObservationEvent` containing actor, from/to
  status, rationale and the evidence hash at that moment. No endpoint can edit
  or delete an event.

## 4. Ground truth is a separate decision

A verified observation is **not** ground truth. Only
`POST /observations/{id}/promote-ground-truth` can create a `GroundTruthRecord`:

- actor must be an ADMIN distinct from both observer and reviewer;
- observation must be `VERIFIED`, non-duplicate and non-synthetic;
- the created record uses `GroundTruthSourceType.FIELD_OBSERVATION` and
  `ProvenanceKind.OPERATIONAL`;
- the link and event are append-only; re-promotion is rejected.

The resulting ground-truth record still starts `UNVERIFIED` and must pass the
existing separate ground-truth verification flow. AI predictions can never be
promoted through this path.

## 5. Human protocol

1. Train observers on category definitions and evidence handling (attestation
   required by the final gate).
2. Record observations with time, location, category and evidence.
3. Assign an independent reviewer; reviewer must not be the observer.
4. Reviewer accepts, rejects or requests revision with a written rationale.
5. Only a distinct administrator promotes accepted observations to ground
   truth; a second reviewer verifies the GT record.
6. Monitor reviewer disagreement and revision rate as operational signals.

## 6. Current state

| Item | Status |
| --- | --- |
| Observation workflow and revision history | IMPLEMENTED / AUTOMATED-TESTED |
| Explicit ground-truth promotion | IMPLEMENTED / AUTOMATED-TESTED |
| Operational field observers trained | BLOCKED |
| Operational field observations collected | BLOCKED (0 records) |
| Human-verified Dhaka ground truth | BLOCKED (0 records) |
| Model predictions used as ground truth | Prohibited; no such path exists |
