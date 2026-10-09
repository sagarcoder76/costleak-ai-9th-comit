"""Password hashing + signed tokens, using only the standard library.

Deliberately dependency-free: PBKDF2-HMAC-SHA256 for passwords and a compact
HMAC-signed JWT-style token for sessions.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from .config import SECRET_KEY, TOKEN_TTL_HOURS

ITERATIONS = 180_000


# ------------------------------------------------------------- passwords --
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def password_problems(password: str) -> list[str]:
    out = []
    if len(password) < 8:
        out.append("at least 8 characters")
    if not any(c.isalpha() for c in password):
        out.append("at least one letter")
    if not any(c.isdigit() for c in password):
        out.append("at least one number")
    return out


# ---------------------------------------------------------------- tokens --
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(payload: dict, ttl_hours: int | None = None) -> str:
    body = {**payload, "iat": int(time.time()),
            "exp": int(time.time()) + (ttl_hours or TOKEN_TTL_HOURS) * 3600}
    raw = _b64e(json.dumps(body, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        raw, sig = token.split(".")
        expected = _b64e(hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        body = json.loads(_b64d(raw))
        if body.get("exp", 0) < time.time():
            return None
        return body
    except Exception:
        return None
