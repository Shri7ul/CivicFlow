# CivicFlow — Architecture Review

Date: 2026-11-26
Scope: assessment of the *existing* architecture and whether evidence justifies changing it. Conclusion: the modular-monolith architecture is sound and is **retained**; defects found are implementation and contract defects, not architectural ones.

## 1. Current architecture (as implemented)

```
Next.js 16 App Router (frontend/)
  └─ Server proxy (src/proxy.ts) — cookie-based route gating
  └─ AuthProvider — Supabase SSR session, token, profile lifecycle
  └─ Feature modules (incidents, map, risk, decisions, operations, validation, pilot)
  └─ lib/api/* — typed API client, error classification, upload helper
                │ HTTPS + bearer JWT
                ▼
FastAPI app (backend/app)
  └─ api/v1/router.py — 15 endpoint modules under /api/v1
  └─ auth/ — JWT verifier (asymmetric only), bearer extraction, RBAC dependencies
  └─ services/ — domain logic (incidents, profiles, risk, decisions, operations, phase9–14)
  └─ models/ + alembic/ — SQLAlchemy 2.x, 24 linear migrations
  └─ core/ — config, exceptions, middleware, logging, request context
                │ SQL / psycopg
                ▼
Supabase PostgreSQL/PostGIS + Supabase Auth + Supabase Storage
```

Deployment: Vercel (frontend), Render Free web service (backend), Supabase (data/auth/storage). Both web origins verified live this sprint.

## 2. Architectural strengths (evidence-backed)

1. **Backend authority is real.** Every endpoint declares an auth dependency; no endpoint trusts a client-supplied role. `backend/app/auth/dependencies.py` derives identity from verified JWT `sub` and reads role from the DB `Profile`, never from JWT claims or request payloads.
2. **Consistent error envelope.** `core/exceptions.py` produces `{"error":{"code","message","details"}}` for `AppError`, HTTP exceptions, validation errors and unhandled exceptions. Verified by `tests/test_errors.py`.
3. **Domain isolation.** Risk, decisions, operations, validation and Phase 9–14 modules are separate services with their own state machines. Duplicate `assess_readiness` variants are context-specific (governance, Dhaka, Phase 14), not accidental copies.
4. **Health separation.** Liveness, database (`SELECT 1`), readiness, and dependencies are distinct endpoints; no health check writes to the DB.
5. **Research/pilot separation.** Decision and Phase 14 responses explicitly set `execution_authorized=False`, `dispatch_performed=False`, `reservations_created=False`. Models are `RESEARCH_ONLY`; activation is gated. No architectural change is warranted here.
6. **Green CI baseline.** 316 backend + 132 frontend tests pass; typecheck, lint, build clean.

## 3. Defects that are implementation/contract level, not architectural

| Defect | Why it is not an architecture problem | Location |
| --- | --- | --- |
| `/risk/cells` returns `response_model=None` for a union type | Single endpoint annotation; the service and schema already exist | `risk.py:204-207` |
| Observation submit discards its body | One handler executes `del payload`; service API is correct | `phase14.py:229` |
| Validation correlation/decision endpoints leak engine errors as 500 | Missing `try/except ValidationError` unlike sibling endpoints | `validation.py:278-299` |
| Phase 10 docstring contradicts permissions | Documentation drift; route dependencies are deliberate | `phase10.py:3-4` vs mutating routes |
| Geolocation/glyphs blocked by headers | Browser security config, not app structure | `next.config.ts:21-26,47` |
| Incident form defaults to fabricated coordinates | Form state bug, not data-model design | `report-incident-form.tsx:34-35` |
| Nav not role-aware | Presentation layer omission; backend already enforces | `auth-nav.tsx:24-95` |
| Generic 401/403 handling absent | Missing cross-cutting UI state, not a service defect | `auth-provider.tsx:216-226` |
| Password recovery missing | Missing feature, not a broken one | no source |

## 4. Architectural limitations that require operator action (no code change)

1. **In-process rate limiting.** `_FixedWindowLimiter` is per-process and keyed on socket peer. Behind Render's proxy all users can share one quota, and a horizontally scaled deployment needs edge enforcement. The middleware comment explicitly states this is single-instance only. Changing to trust `X-Forwarded-For` without an explicit trusted-proxy configuration would create a spoofable key and weaken security; therefore no code change is made. Operator should enforce rate limits at the edge, or explicitly enable a trusted-proxy mode in a follow-up with its own threat model.
2. **RLS enforcement.** Migrations contain policies, but documentation reports the app connects as `postgres`, which bypasses RLS. Backend authorization is enforced in application code; least-privilege DB role is provider-side.
3. **TrustedHostMiddleware absent.** No host allowlist at the app layer; relying on platform routing.
4. **Live migration status.** `0023`/`0024` remain pending per existing docs; no migration is run in this sprint (no backup/restore verification, no authorization).
5. **Build-time environment coupling.** `connect-src` in CSP is computed from `NEXT_PUBLIC_API_BASE_URL` at build time. A Vercel build without that variable silently drops the API origin. Verified live header is correct, but the operator must preserve the variable on every build.

## 5. Test architecture gap

Backend tests use in-memory SQLite (`tests/conftest.py:57`), so PostgreSQL/PostGIS-specific behavior (spatial indexes, RLS) is not truly validated. Frontend tests use Vitest `environment: "node"`, so no DOM interaction testing exists; `AuthProvider`, `AuthNav`, `AuthGuard`, the callback page, `proxy.ts`, map and incident UI are untested. These are coverage gaps, not architecture defects — adding browser-level tests would require new dev dependencies (jsdom / Testing Library / Playwright), which is a deliberate follow-up decision, not a silent redesign.

## 6. Decision

**Retain the architecture.** This sprint fixes the enumerated implementation and contract defects, completes the missing auth feature, and adds tests for the changed behavior. It does not replace the modular monolith, change the ORM, alter role semantics, or bypass any gate.
