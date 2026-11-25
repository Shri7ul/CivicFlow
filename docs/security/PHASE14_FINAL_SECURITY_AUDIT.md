# Phase 14 — Final Security and Adversarial Audit

Date: 2026-11-25. Scope: repository implementation plus read-only live
database inspection. No production HTTP endpoint was available; live web-layer
verification is NOT_ASSESSED.

## 1. Controls verified in code and automated tests

| Control | Result |
| --- | --- |
| Geographic isolation | Observations resolve context server-side; NYC points map to `US-NYC`, outside points are rejected; client cannot set context. PASS (automated) |
| RBAC on all Phase 14 routes | Reads require WORKER/ADMIN; boundary registration, source authorization/revocation, attestation, baseline recording and shutdown require ADMIN. PASS (automated) |
| RLS | Migration `0024` enables RLS, revokes anon/authenticated writes and grants read-only SELECT policies on every new table (PostgreSQL). Live check confirmed RLS on `pilots` and `evidence_snapshots`; new tables not deployed. PARTIAL / deployment BLOCKED |
| Unauthorized pilot activation | Final gate is recomputed server-side during ACTIVATE/RESUME; client-supplied `ready` is rejected as extra field; missing evidence returns `phase14_readiness_not_met`. PASS (automated) |
| Unauthorized approval | Boundary verification/approval and GT promotion enforce separation of duties. PASS (automated) |
| Client-side context manipulation | Boundary context is derived from bbox and cross-checked; observation context from point. PASS (automated) |
| Evidence modification / provenance tampering | No update/delete endpoints for Phase 14 audit events; event retains original evidence hash after direct DB mutation. PASS (automated) |
| Hash integrity | Boundary hash is server-computed from a canonical document; source hashes validated as 64-hex; tampered hash is rejected by schema. PASS (automated) |
| Reviewer authorization | Only the assigned reviewer or an admin can decide; observer cannot self-verify. PASS (automated) |
| Pilot lifecycle manipulation | TERMINATE allowed only from governed states; reason required; shutdown is idempotence-protected. PASS (automated) |
| Model activation bypass | Model-status endpoint is descriptive; no promotion route exists; final gate blocks pilot activation. PASS (automated) |
| Readiness gate bypass | No hardcoded PASS, no client status; manual attestations alone cannot satisfy derived categories. PASS (automated) |
| Duplicate evidence | Observer+source-reference uniqueness; explicit duplicate marking sets REJECTED/DUPLICATE. PASS (automated) |
| Cross-pilot / cross-geography access | Staff reads are global by design; writes are scoped by pilot/context checks, and review assignment remains pilot-bound from Phase 10. PARTIAL — no multi-tenant citizen access to Phase 14 records |
| Audit log integrity | Append-only event tables with no mutation endpoints; no deletes anywhere in Phase 14. PASS (automated / structural) |
| Sensitive information leakage | Serializers omit raw file bytes; secrets remain in git-ignored env files and are never printed. PASS (code review) |
| SSRF | Source endpoint validator blocks private, loopback, link-local, multicast and metadata-style hosts. PASS (automated) |
| File upload abuse | Phase 14 introduces no upload endpoint; evidence is referenced by hash/reference only. N/A |
| Rate limiting / production config | Phase 13 controls retained and covered by existing tests. PASS (automated) |

## 2. Adversarial cases executed

- `ACTIVATE` with `{"ready": true}` → 422.
- `ACTIVATE` after Phase 10 gate monkeypatched to PASS but real Phase 14 gate →
  409 `phase14_readiness_not_met`.
- Worker registering boundary, authorizing source, recording attestation or
  baseline, or shutting down a pilot → 403.
- Observer self-verification, self-assignment, self-promotion → 403.
- Non-authoritative (OSM_RESEARCH) boundary approval → 422.
- Duplicate source reference → 409; duplicate observation → REJECTED/DUPLICATE.
- Fabricated metric without labels → 422 `fabricated_metric`.
- Private endpoint → 422.
- Early incident processing resume → 409.
- PATCH/DELETE on audit event paths → 404/405.

## 3. Open security gaps

1. New Phase 14 tables are not deployed to the live database; live RLS on those
   tables is BLOCKED / NOT_ASSESSED.
2. No live frontend/backend HTTP verification was possible (no documented
   deployment URL); web-layer headers, request IDs and rate limiting remain
   NOT_ASSESSED live.
3. Append-only is enforced by application design and RLS read grants; dedicated
   database triggers for the new event tables were not added in migration 0024.
   Direct service-role writes are therefore trusted, as in earlier phases.
4. No independent penetration test or human security sign-off was performed.
