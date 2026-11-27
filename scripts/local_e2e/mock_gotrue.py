"""Local-only GoTrue/JWKS stand-in for CivicFlow end-to-end testing.

This server exists solely to make a *fully isolated* local browser test
possible. It:

* reuses a gitignored local ES256 keypair so tokens survive restarts,
* implements the small subset of the GoTrue API used by supabase-js v2
  (signup, password/refresh grants, user, logout, JWKS), and
* issues real, verifiable ES256 JWTs that the backend accepts when it is
  pointed at this server through environment variables.

It must only ever be bound to 127.0.0.1 and must never be used for production.
Accounts are synthetic and live in memory for the lifetime of the process.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import jwt
from jwt.algorithms import ECAlgorithm
from cryptography.hazmat.primitives.asymmetric import ec

HOST = "127.0.0.1"
PORT = int(os.environ.get("LOCAL_E2E_PORT", "54321"))
AUDIENCE = "authenticated"
ISSUER = f"http://{HOST}:{PORT}/auth/v1"
KID = "local-e2e-es256"
ANON_KEY = "local-e2e-anon-key-not-a-real-credential-0001"

from cryptography.hazmat.primitives import serialization
from pathlib import Path

_KEY_PATH = Path(__file__).resolve().parents[2] / ".cache" / "local_e2e" / "mock_key.pem"
if _KEY_PATH.exists():
    PRIVATE_KEY = serialization.load_pem_private_key(_KEY_PATH.read_bytes(), password=None)
else:
    PRIVATE_KEY = ec.generate_private_key(ec.SECP256R1())
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PATH.write_bytes(
        PRIVATE_KEY.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
PUBLIC_JWK = ECAlgorithm.to_jwk(PRIVATE_KEY.public_key(), as_dict=True)
PUBLIC_JWK.update({"kid": KID, "alg": "ES256", "use": "sig"})

_USERS: dict[str, dict[str, Any]] = {}
_PASSWORD_HASHES: dict[str, str] = {}
_SESSIONS: dict[str, dict[str, Any]] = {}


def _now() -> int:
    return int(time.time())


def _user(email: str, full_name: str | None) -> dict[str, Any]:
    created = _now()
    return {
        "id": str(uuid.uuid4()),
        "aud": AUDIENCE,
        "role": "authenticated",
        "email": email,
        "email_confirmed_at": created,
        "phone": "",
        "confirmed_at": created,
        "last_sign_in_at": created,
        "app_metadata": {"provider": "email", "providers": ["email"]},
        "user_metadata": {"full_name": full_name or ""},
        "identities": [],
        "created_at": created,
        "updated_at": created,
    }


def _token(user: dict[str, Any]) -> str:
    now = _now()
    return jwt.encode(
        {
            "sub": user["id"],
            "email": user["email"],
            "role": "authenticated",
            "aud": AUDIENCE,
            "iss": ISSUER,
            "iat": now,
            "exp": now + 3600,
        },
        PRIVATE_KEY,
        algorithm="ES256",
        headers={"kid": KID, "alg": "ES256"},
    )


def _session(user: dict[str, Any]) -> dict[str, Any]:
    access = _token(user)
    refresh = uuid.uuid4().hex
    record = {
        "access_token": access,
        "token_type": "bearer",
        "expires_in": 3600,
        "expires_at": _now() + 3600,
        "refresh_token": refresh,
        "user": user,
    }
    _SESSIONS[refresh] = {"user": user, "access": access, "expires_at": record["expires_at"]}
    return record


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[mock-gotrue] {self.command} {self.path} -> {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "86400")

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _empty(self, status: int = 204) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            return {}

    def _bearer_user(self) -> dict[str, Any] | None:
        header = self.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        token = header.split(None, 1)[1]
        try:
            claims = jwt.decode(
                token,
                ECAlgorithm.from_jwk(json.dumps(PUBLIC_JWK)),
                algorithms=["ES256"],
                audience=AUDIENCE,
                issuer=ISSUER,
            )
        except Exception:
            return None
        return _USERS.get(str(claims.get("sub")))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._empty(204)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/auth/v1/.well-known/jwks.json":
            return self._json({"keys": [PUBLIC_JWK]})
        if path == "/auth/v1/settings":
            return self._json(
                {
                    "external_email_enabled": False,
                    "disable_signup": False,
                    "mailer_allow_external_signup": False,
                    "email_auth_enabled": True,
                }
            )
        if path == "/auth/v1/user":
            user = self._bearer_user()
            if user is None:
                return self._json({"message": "Invalid token"}, 401)
            return self._json(user)
        return self._json({"message": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        query = parse_qs(urlparse(self.path).query)
        body = self._body()

        if path == "/auth/v1/signup":
            email = str(body.get("email", "")).strip().lower()
            password = str(body.get("password", ""))
            if not email or len(password) < 8:
                return self._json({"message": "Invalid signup payload"}, 400)
            existing = next((u for u in _USERS.values() if u["email"] == email), None)
            if existing:
                return self._json({"message": "User already registered"}, 422)
            meta = body.get("data") or {}
            user = _user(email, str(meta.get("full_name") or ""))
            _USERS[user["id"]] = user
            _PASSWORD_HASHES[user["id"]] = hashlib.sha256(password.encode()).hexdigest()
            # GoTrue returns session fields at the top level for /signup;
            # supabase-js derives `session` from access_token at that level.
            return self._json(_session(user))

        if path == "/auth/v1/token":
            grant = (query.get("grant_type") or [""])[0]
            if grant == "password":
                email = str(body.get("email", "")).strip().lower()
                password = str(body.get("password", ""))
                user = next((u for u in _USERS.values() if u["email"] == email), None)
                if not user or _PASSWORD_HASHES.get(user["id"]) != hashlib.sha256(password.encode()).hexdigest():
                    return self._json({"message": "Invalid login credentials"}, 400)
                user["last_sign_in_at"] = _now()
                return self._json(_session(user))
            if grant == "refresh_token":
                refresh = str(body.get("refresh_token", ""))
                record = _SESSIONS.get(refresh)
                if not record:
                    return self._json({"message": "Invalid refresh token"}, 400)
                user = record["user"]
                return self._json(_session(user))
            return self._json({"message": "Unsupported grant type"}, 400)

        if path == "/auth/v1/logout":
            return self._empty(204)

        return self._json({"message": "not found"}, 404)


if __name__ == "__main__":
    print(f"local GoTrue mock on http://{HOST}:{PORT} (issuer {ISSUER})", flush=True)
    print(f"JWKS kid={KID}; accounts are in-memory and synthetic only", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
