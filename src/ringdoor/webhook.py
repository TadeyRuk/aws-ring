from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def sign(raw_body: bytes, key: str) -> str:
    return "sha256=" + hmac.new(key.encode(), raw_body, hashlib.sha256).hexdigest()


def verify_signature(raw_body: bytes, header: Optional[str], key: Optional[str]) -> bool:
    """X-Signature = 'sha256=' + hex(HMAC-SHA256(raw body bytes, partner HMAC key)).
    Must be computed over the bytes exactly as received (never re-serialized JSON)."""
    if not key:
        return True  # signature checking disabled (local dev only)
    if not header:
        return False
    return hmac.compare_digest(header.strip().lower(), sign(raw_body, key).lower())
