"""Alembic migration configuration and execution tests."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.models import Base

BACKEND = Path(__file__).resolve().parents[2]


def _config(database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", database_url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("prepend_sys_path", str(BACKEND))
    return config


def test_offline_postgresql_migration_renders_postgis_and_rls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(
        "postgresql+psycopg://user:pass@localhost:5432/civicflow", monkeypatch
    )
    command.upgrade(config, "head", sql=True)
    output = capsys.readouterr().out

    assert "CREATE EXTENSION IF NOT EXISTS postgis" in output
    assert "geography(POINT,4326)" in output
    assert "geometry(GEOMETRY,4326)" in output
    assert "geometry(POLYGON,4326)" in output
    assert "USING gist (location)" in output
    assert "ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY" in output
    assert "CREATE POLICY profiles_select_self" in output
    assert "prevent_profile_privileged_changes" in output
    assert "CREATE TABLE incidents" in output
    assert "CREATE TABLE incident_status_events" in output
    assert "CREATE TABLE role_change_audits" in output
    assert "incident_status_events_read_visible_incident" in output
    assert "REVOKE ALL PRIVILEGES ON TABLE public.incident_status_events" in output
    assert "GRANT SELECT ON TABLE public.incident_status_events" in output
    assert "civicflow_evidence_read" in output
    assert "ck_incident_evidence_allowed_mime_type" in output
    assert "CREATE TABLE incident_relationships" in output
    assert "incident_relationships_read_visible_pair" in output
    assert "REVOKE ALL PRIVILEGES ON TABLE public.incident_relationships" in output
    assert "REVOKE ALL PRIVILEGES ON TABLE public.profiles" in output
    assert "GRANT SELECT ON TABLE public.profiles" in output


def test_sqlite_upgrade_and_downgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "migration.db"
    config = _config(f"sqlite:///{db_path.as_posix()}", monkeypatch)

    command.upgrade(config, "head")

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        version = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()[0]
    assert "incidents" in tables
    assert "role_change_audits" in tables
    assert "alembic_version" in tables
    assert version == "0008_confidence_check_name"

    # Every model column must exist in the migrated schema.
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    inspector = inspect(engine)
    for table in Base.metadata.tables.values():
        migrated_columns = {
            column["name"] for column in inspector.get_columns(table.name)
        }
        assert migrated_columns == {column.name for column in table.columns}, (
            table.name
        )
    engine.dispose()

    command.downgrade(config, "base")
    with sqlite3.connect(db_path) as connection:
        remaining = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert "incidents" not in remaining
    assert "alembic_version" in remaining


def test_migration_files_are_reproducible_and_ordered() -> None:
    versions = sorted((BACKEND / "alembic" / "versions").glob("*.py"))
    names = [path.name for path in versions]
    assert names == [
        "0001_initial_schema.py",
        "0002_auth_rls.py",
        "0003_acl_hardening.py",
        "0004_incident_lifecycle.py",
        "0005_map_evidence_storage.py",
        "0006_incident_intelligence.py",
        "0007_relationship_checks.py",
        "0008_confidence_check_name.py",
    ]
    assert "postgis" in (versions[0].read_text(encoding="utf-8")).lower()
    rls = versions[1].read_text(encoding="utf-8")
    assert "auth.uid()" in rls
    assert "ENABLE ROW LEVEL SECURITY" in rls
    acl = versions[2].read_text(encoding="utf-8")
    assert "REVOKE ALL PRIVILEGES" in acl
    assert "TO authenticated" in acl
    assert "service_role" in acl  # documented as intentionally unchanged
    lifecycle = versions[3].read_text(encoding="utf-8")
    assert "incident_status_events" in lifecycle
    assert "is_worker_or_admin" in lifecycle
    assert "GRANT SELECT" in lifecycle
    evidence_storage = versions[4].read_text(encoding="utf-8")
    assert "incident-evidence" in evidence_storage
    assert "civicflow_evidence_read" in evidence_storage
    assert "REVOKE INSERT ON TABLE public.incident_evidence" in evidence_storage
    assert "ck_incident_evidence_allowed_mime_type" in evidence_storage
    intelligence = versions[5].read_text(encoding="utf-8")
    assert "incident_relationships" in intelligence
    assert "incident_relationships_read_visible_pair" in intelligence
    assert "REVOKE ALL PRIVILEGES" in intelligence
    assert "relationship_logical_unique" in intelligence
    checks = versions[6].read_text(encoding="utf-8")
    assert "RENAME CONSTRAINT" in checks
    final_check = versions[7].read_text(encoding="utf-8")
    assert "confidence_range" in final_check
