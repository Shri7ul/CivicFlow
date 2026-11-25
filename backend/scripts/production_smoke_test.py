#!/usr/bin/env python3
"""Read-only production smoke tests for a deployed CivicFlow backend.

This script performs NO writes: it never creates incidents, ground truth,
pilot data, authorizations or accounts, and never changes production state.
Authenticated checks are optional and require a pre-existing read-only token
supplied by the operator (env `CIVICFLOW_SMOKE_TOKEN` or `--token`).

Usage:
    python scripts/production_smoke_test.py --base-url https://<backend-host>

Exit code 0 means every executed check passed; 1 means at least one failed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

API_PREFIX = "/api/v1"
REQUEST_ID_HEADER = "X-Request-ID"


@dataclass
class Result:
    name: str
    passed: bool
    detail: str


class Smoker:
    def __init__(self, base_url: str, timeout: float, token: str | None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = token
        self.results: list[Result] = []

    def _request(
        self,
        path: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        req = urllib.request.Request(
            self.base_url + path,
            method=method,
            headers=headers or {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, dict(resp.headers.items()), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def check(self, name: str, condition: bool, detail: str) -> None:
        self.results.append(Result(name, bool(condition), detail))

    def _json(self, body: bytes) -> dict[str, Any]:
        try:
            value = json.loads(body)
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    # -- checks ---------------------------------------------------------

    def check_https(self, expected_env: str) -> None:
        scheme = urlparse(self.base_url).scheme
        self.check(
            "https",
            scheme == "https" if expected_env == "production" else scheme in {"http", "https"},
            f"scheme={scheme!r}, expected_env={expected_env!r}",
        )

    def check_health(self, expected_env: str) -> None:
        status, headers, body = self._request(f"{API_PREFIX}/health")
        payload = self._json(body)
        self.check(
            "health",
            status == 200 and payload.get("status") == "healthy",
            f"status={status}, body={payload}",
        )
        self.check(
            "health.environment",
            payload.get("environment") == expected_env,
            f"expected={expected_env!r}, actual={payload.get('environment')!r}",
        )
        self.check(
            "request_id",
            bool(headers.get(REQUEST_ID_HEADER.lower())),
            f"header present={bool(headers.get(REQUEST_ID_HEADER.lower()))}",
        )

    def check_database(self) -> None:
        status, _, body = self._request(f"{API_PREFIX}/health/database")
        payload = self._json(body)
        self.check(
            "database",
            status == 200 and payload.get("database") == "reachable",
            f"status={status}, body={payload}",
        )

    def check_ready(self) -> None:
        status, _, body = self._request(f"{API_PREFIX}/health/ready")
        payload = self._json(body)
        self.check(
            "ready",
            status == 200 and payload.get("status") == "ready",
            f"status={status}, body={payload}",
        )

    def check_dependencies(self) -> None:
        status, _, body = self._request(f"{API_PREFIX}/health/dependencies")
        payload = self._json(body)
        self.check(
            "dependencies",
            status == 200
            and payload.get("status") == "operational"
            and payload.get("auth_verification_configured") is True,
            f"status={status}, body={payload}",
        )

    def check_docs_closed(self, expected_env: str) -> None:
        if expected_env != "production":
            self.results.append(
                Result(
                    "production_docs_closed",
                    True,
                    "SKIPPED: docs exposure is only a production concern",
                )
            )
            return
        for path in ("/docs", "/openapi.json"):
            status, _, _ = self._request(path)
            self.check(
                f"production_docs_closed{path}",
                status != 200,
                f"{path} returned {status} (200 would expose API docs in production)",
            )

    def check_auth_enforced(self) -> None:
        status, _, _ = self._request(f"{API_PREFIX}/auth/me")
        self.check(
            "unauthenticated_rejected",
            status in {401, 403},
            f"/auth/me returned {status} without credentials",
        )

    def check_cors(self) -> None:
        headers = {
            "Origin": "https://untrusted.example.invalid",
            "Access-Control-Request-Method": "GET",
        }
        status, resp_headers, _ = self._request(
            f"{API_PREFIX}/health", method="OPTIONS", headers=headers
        )
        allowed = resp_headers.get("access-control-allow-origin")
        self.check(
            "cors_not_wildcard",
            allowed != "*" and allowed != headers["Origin"],
            f"preflight status={status}, allow-origin={allowed!r}",
        )

    def check_authenticated_reads(self) -> None:
        if not self.token:
            self.results.append(
                Result(
                    "authenticated_reads",
                    True,
                    "SKIPPED: no CIVICFLOW_SMOKE_TOKEN / --token supplied",
                )
            )
            return

        status, _, body = self._request(
            f"{API_PREFIX}/governance/geography/contexts", headers=self._auth_headers()
        )
        payload = self._json(body)
        keys = set()
        if isinstance(payload.get("items"), list):
            keys = {
                item.get("context_key")
                for item in payload["items"]
                if isinstance(item, dict)
            }
        self.check(
            "geography_contexts",
            status == 200 and {"US-NYC", "BD-DHAKA"}.issubset(keys),
            f"status={status}, keys={sorted(k for k in keys if k)}",
        )

        status, _, body = self._request(
            f"{API_PREFIX}/governance/phase14/model-status", headers=self._auth_headers()
        )
        payload = self._json(body)
        self.check(
            "model_status_research_only",
            status == 200 and "RESEARCH" in str(payload.get("readiness_level", "")).upper(),
            f"status={status}, body={payload}",
        )

        status, _, body = self._request(
            f"{API_PREFIX}/governance/phase14/readiness", headers=self._auth_headers()
        )
        payload = self._json(body)
        self.check(
            "phase14_gate_blocks_activation",
            status == 200 and payload.get("ready_for_activation") is False,
            f"status={status}, ready_for_activation={payload.get('ready_for_activation')}",
        )

    def run(self, expected_env: str) -> int:
        self.check_https(expected_env)
        self.check_health(expected_env)
        self.check_database()
        self.check_ready()
        self.check_dependencies()
        self.check_docs_closed(expected_env)
        self.check_auth_enforced()
        self.check_cors()
        self.check_authenticated_reads()

        width = max(len(r.name) for r in self.results)
        for result in self.results:
            label = "PASS" if result.passed else "FAIL"
            if result.detail.startswith("SKIPPED"):
                label = "SKIP"
            print(f"[{label}] {result.name:<{width}} | {result.detail}")
        failed = [r for r in self.results if not r.passed]
        print(f"\n{len(self.results) - len(failed)} passed, {len(failed)} failed")
        return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Deployed backend origin")
    parser.add_argument(
        "--expected-env",
        default="production",
        help="Expected APP_ENV reported by /health (default: production)",
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument(
        "--token",
        default=os.environ.get("CIVICFLOW_SMOKE_TOKEN"),
        help="Optional read-only bearer token for authenticated checks",
    )
    args = parser.parse_args()
    return Smoker(args.base_url, args.timeout, args.token).run(args.expected_env)


if __name__ == "__main__":
    sys.exit(main())
