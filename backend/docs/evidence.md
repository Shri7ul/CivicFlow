# Incident evidence and private Storage

Evidence is a Phase 3 capability layered on the existing `incident_evidence`
table. The browser never receives the Supabase service-role key and never writes
to Storage directly.

## Data model

`incident_evidence` stores:

- `incident_id` (FK to `incidents`, `RESTRICT`)
- `uploaded_by` (FK to `profiles`, `RESTRICT`)
- `storage_path` (unique server-generated object key)
- `file_name` (sanitized display name)
- `mime_type` (`image/jpeg`, `image/png`, or `image/webp`)
- `file_size` (bytes, positive and ≤ 10 MB)
- `created_at`

Migration `0005_map_evidence_storage` adds the MIME/size CHECK constraints and a
composite `(incident_id, created_at)` index. It also revokes direct authenticated
INSERT on `incident_evidence`; authenticated retains only SELECT, filtered by the
existing incident-visibility RLS policy.

## Authorization and Storage boundary

- Upload/list/metadata/signing endpoints require an active profile.
- The incident visibility rule is checked **before** metadata access, upload, or
  signed URL issuance. Another Citizen receives `404 incident_not_found` rather
  than learning that an incident or evidence exists.
- Bytes are uploaded with the backend-only service role to the private
  `incident-evidence` bucket.
- The bucket is not public and has a 10 MB object limit plus a JPEG/PNG/WebP
  allowlist.
- Signed preview URLs expire after 300 seconds by default. Signing happens only
  after backend authorization.
- There is no browser write policy for the bucket. Direct authenticated Storage
  reads are denied by the absence of a `storage.objects` policy.

### Hosted Supabase ownership note

Migration `0005` attempts to create a visibility-scoped `storage.objects` SELECT
policy. On the configured Supabase project, `storage.objects` is owned by
`supabase_storage_admin`, not the migration role (`postgres`), so the policy block
is skipped with a notice. Direct authenticated reads remain deny-all, which is
stricter than broad client access; backend signed URLs still provide authorized
viewing. If a project-level policy is required, apply the policy below in the
Supabase SQL editor with a role that owns `storage.objects` (or through the
dashboard):

```sql
create policy civicflow_evidence_read
on storage.objects
for select
to authenticated
using (
  bucket_id = 'incident-evidence'
  and exists (
    select 1
    from public.incident_evidence e
    join public.incidents i on i.id = e.incident_id
    where e.storage_path = storage.objects.name
      and (i.reporter_id = auth.uid() or public.is_worker_or_admin())
  )
);
```

Do not add INSERT/UPDATE/DELETE policies for browser clients; writes are
backend-only.

## Upload validation

`POST /api/v1/incidents/{incident_id}/evidence`

- Multipart field: `files` (repeatable).
- 1–5 files per request.
- Per-file limit: 10 MB (`EVIDENCE_MAX_FILE_SIZE_BYTES`).
- MIME is detected from file signatures, not trusted `Content-Type`:
  JPEG (`FF D8 FF`), PNG signature, and WebP (`RIFF…WEBP`).
- Empty files and arbitrary types such as SVG/text are rejected.
- Display names are reduced to a basename, control characters are removed, and
  unsafe characters are replaced. The display name is never used in the object
  key.
- Each object key is `{incident_uuid}/{random_hex}.{jpg|png|webp}`.
- All files are validated before any object is uploaded. If an upload or DB
  commit fails, already-uploaded objects are deleted on a best-effort basis and
  the transaction is rolled back.

Response (`201`) is a list of safe metadata records:

```json
[
  {
    "id": "…",
    "incident_id": "…",
    "file_name": "photo.png",
    "mime_type": "image/png",
    "file_size": 12345,
    "uploader": { "id": "…", "full_name": "Citizen" },
    "created_at": "2026-11-24T00:00:00Z"
  }
]
```

Other endpoints:

- `GET /api/v1/incidents/{id}/evidence` — metadata for a visible incident.
- `GET /api/v1/incidents/{id}/evidence/{evidence_id}/url` — signed URL response
  `{ "signed_url": "...", "expires_in": 300 }`.
- Incident detail responses include `evidence` alongside lifecycle history.

## Error codes

| Code | Status | Meaning |
| --- | --- | --- |
| `evidence_required` | 422 | No files supplied |
| `too_many_evidence_files` | 422 | More than five files |
| `evidence_too_large` | 413 | File exceeds 10 MB |
| `empty_evidence_file` | 422 | Zero-byte file |
| `unsupported_evidence_type` | 422 | Signature is not JPEG/PNG/WebP |
| `evidence_not_found` | 404 | Evidence is not on the visible incident |
| `evidence_storage_unavailable` | 503 | Storage/service-role unavailable |

## Frontend

`frontend/src/components/incidents/evidence-gallery.tsx`:

- client-side preflight for count/type/size;
- multipart upload through `AuthProvider.uploadRequest` (XMLHttpRequest progress,
  bearer token in the Authorization header, never the URL);
- progress bar and retry using the retained file selection;
- signed preview links fetched per item, with a refresh action for expiry;
- images use `referrerPolicy="no-referrer"` and are opened in a new tab when
  clicked.

## Verification boundary

Live validation on 2026-11-23 verified real Auth users, a real upload to the
private bucket, signature-based MIME rejection, filename sanitization,
server-generated paths, signed URL bytes, direct Storage read denial, and
cross-Citizen denial. The hosted `storage.objects` policy itself could not be
created by the migration role; see the ownership note above.
