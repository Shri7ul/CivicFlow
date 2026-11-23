"""Phase 3 evidence hardening and private Storage setup.

Revision ID: 0005_map_evidence_storage
Revises: 0004_incident_lifecycle
Create Date: 2026-11-24

Evidence uploads are performed by the FastAPI backend with the service role.
The browser never receives the service-role key and direct authenticated table
INSERTs are revoked. Storage is private; the backend issues short-lived signed
URLs only after incident authorization.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_map_evidence_storage"
down_revision: Union[str, None] = "0004_incident_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BUCKET = "incident-evidence"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_MIME_TYPES = "ARRAY['image/jpeg','image/png','image/webp']::text[]"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    op.execute(
        "ALTER TABLE public.incident_evidence "
        "ADD CONSTRAINT ck_incident_evidence_file_size_max "
        f"CHECK (file_size <= {MAX_FILE_SIZE})"
    )
    op.execute(
        "ALTER TABLE public.incident_evidence "
        "ADD CONSTRAINT ck_incident_evidence_allowed_mime_type "
        "CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incident_evidence_incident_created "
        "ON public.incident_evidence (incident_id, created_at)"
    )

    # Evidence writes go through the backend only. SELECT remains for the
    # existing incident-visibility RLS policy.
    op.execute(
        "REVOKE INSERT ON TABLE public.incident_evidence FROM authenticated"
    )
    op.execute(
        "REVOKE INSERT ON TABLE public.incident_evidence FROM anon"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.incident_evidence TO authenticated"
    )

    # Create the private bucket when the Supabase Storage schema is present.
    # The same settings are enforced by the backend on every upload.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('storage.buckets') IS NOT NULL THEN
                INSERT INTO storage.buckets
                    (id, name, public, file_size_limit, allowed_mime_types)
                VALUES
                    ('{BUCKET}', '{BUCKET}', false, {MAX_FILE_SIZE},
                     {ALLOWED_MIME_TYPES})
                ON CONFLICT (id) DO UPDATE SET
                    public = false,
                    file_size_limit = EXCLUDED.file_size_limit,
                    allowed_mime_types = EXCLUDED.allowed_mime_types;
            END IF;
        END;
        $$;
        """
    )

    # Private object reads are allowed only for evidence attached to an
    # incident the caller can already see. No INSERT/UPDATE/DELETE policy is
    # provided; only the backend service role may mutate objects.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('storage.objects') IS NOT NULL THEN
                BEGIN
                    EXECUTE 'ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY';
                    EXECUTE 'DROP POLICY IF EXISTS civicflow_evidence_read ON storage.objects';
                    EXECUTE $policy$
                        CREATE POLICY civicflow_evidence_read
                        ON storage.objects
                        FOR SELECT
                        TO authenticated
                        USING (
                            bucket_id = '{BUCKET}'
                            AND EXISTS (
                                SELECT 1
                                FROM public.incident_evidence e
                                JOIN public.incidents i ON i.id = e.incident_id
                                WHERE e.storage_path = storage.objects.name
                                  AND (
                                      i.reporter_id = auth.uid()
                                      OR public.is_worker_or_admin()
                                  )
                            )
                        )
                    $policy$;
                EXCEPTION WHEN insufficient_privilege THEN
                    -- Hosted Supabase owns storage.objects as
                    -- supabase_storage_admin. The bucket remains private and
                    -- has no client write policy; signed URL issuance is
                    -- still backend-authorized. Apply this policy in the
                    -- Supabase dashboard if direct Storage reads are needed.
                    RAISE NOTICE 'Skipping storage.objects policy: caller is not the table owner';
                END;
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    if not _is_postgres():
        return

    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('storage.objects') IS NOT NULL THEN
                BEGIN
                    EXECUTE 'DROP POLICY IF EXISTS civicflow_evidence_read ON storage.objects';
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Skipping storage.objects policy drop: caller is not the table owner';
                END;
            END IF;
        END;
        $$;
        """
    )
    op.execute(
        "DROP INDEX IF EXISTS public.ix_incident_evidence_incident_created"
    )
    op.execute(
        "ALTER TABLE public.incident_evidence "
        "DROP CONSTRAINT IF EXISTS ck_incident_evidence_allowed_mime_type"
    )
    op.execute(
        "ALTER TABLE public.incident_evidence "
        "DROP CONSTRAINT IF EXISTS ck_incident_evidence_file_size_max"
    )
    op.execute(
        "GRANT INSERT ON TABLE public.incident_evidence TO authenticated"
    )
