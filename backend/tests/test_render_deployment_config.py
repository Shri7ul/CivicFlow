"""Render FREE Web Service deployment configuration regression tests.

These guard the failure mode where Render ran `pip install -r requirements.txt`
but no such file existed, and where the blueprint drifted from the code.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def _requirement_lines() -> list[str]:
    path = BACKEND_ROOT / "requirements.txt"
    assert path.is_file(), "backend/requirements.txt must exist for Render builds"
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def test_requirements_matches_pyproject_dependencies() -> None:
    """The Render install file must stay in sync with the declared runtime deps."""
    pyproject = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["dependencies"]
    assert _requirement_lines() == declared


def test_requirements_excludes_development_only_packages() -> None:
    lines = _requirement_lines()
    assert not any(line.lower().startswith("pytest") for line in lines)


def test_render_blueprint_matches_backend_layout() -> None:
    config = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    expected = (
        "plan: free",
        "rootDir: backend",
        "buildCommand: python -m pip install -r requirements.txt",
        "startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT",
        "healthCheckPath: /api/v1/health",
        'value: "3.11"',
        "APP_ENV",
        "DATABASE_URL",
        "SUPABASE_URL",
        "CORS_ORIGINS",
    )
    for fragment in expected:
        assert fragment in config, f"render.yaml is missing {fragment!r}"


def test_python_version_file_agrees_with_blueprint() -> None:
    version_file = BACKEND_ROOT / ".python-version"
    assert version_file.is_file()
    assert version_file.read_text(encoding="utf-8").strip() == "3.11"
    assert 'value: "3.11"' in (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")


def test_fastapi_app_object_exists() -> None:
    source = (BACKEND_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "app = create_app()" in source
