# Phase 14 — Pilot Rollback and Shutdown

Status: **SHUTDOWN CONTROL IMPLEMENTED / NO PILOT SHUT DOWN YET**

## 1. Implemented shutdown control

- `PilotStatus.TERMINATED` and `PilotTransitionAction.TERMINATE` were added to
  the pilot lifecycle (migration `0024`). TERMINATE is allowed only from
  APPROVED, ACTIVE or PAUSED, requires a reason, and appends a `PilotTransition`.
- `POST /api/v1/governance/phase14/pilots/{id}/shutdown` calls that transition
  and writes a `PilotShutdown` record containing preserved-row counts.
- Shutdown sets `model_activation_disabled = true` and
  `reauthorization_required = true`. A second shutdown is rejected.
- No endpoint deletes evidence, snapshots, provenance, audit events, review
  decisions, observations or incidents.

Preserved counts include evidence snapshots, ground truth, field observations,
boundaries, registered sources, review cases, pilot incidents, baseline
comparisons and pilot transitions.

## 2. Rollback matrix

| Layer | Procedure | Data impact |
| --- | --- | --- |
| Application (frontend) | Redeploy the previous immutable build artifact through the approved deployment process | No database change |
| Application (backend) | Redeploy the previous immutable image/tag; do not reset the database | No database change |
| Pilot processing | Admin PAUSE, or CRITICAL-incident interlock, then investigate | No data deleted |
| Pilot termination | `POST .../shutdown` → TERMINATED + `PilotShutdown` | All records preserved |
| Migration `0024` | Reversible in code (`downgrade`) but must not be run against production without authorization and a verified restore point | Drops Phase 14 tables/columns only; no historical evidence deleted by the code |
| Database restore | Restore from a verified backup into a separate database first; never overwrite production during a drill | Requires verified backup (currently BLOCKED) |

## 3. Shutdown checklist

1. Record the reason and the authorizing human identity.
2. Confirm no autonomous action is in flight; the platform has no civic-action
   execution path.
3. Call the shutdown endpoint; verify pilot status is TERMINATED.
4. Verify the `PilotShutdown` record and its preserved counts.
5. Confirm the readiness API reports the pilot as not activatable.
6. Confirm processing interlocks and reviewer queues are reviewed by humans.
7. Archive the evidence/audit export through the existing traceability flow.
8. Record reauthorization requirements; TERMINATED is not resumed by this API.

## 4. Limitations

- Migration rollback is a schema operation, not an evidence rollback. It must
  be planned with a verified backup and deployment authorization.
- No backup or restore drill was available in Phase 14; restore readiness is
  BLOCKED.
- Reauthorization after termination requires a new, explicit human decision;
  no automatic restart exists.
