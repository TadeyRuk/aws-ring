from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

API_BASE = "https://api.amazonvision.com"
TOKEN_URL = "https://oauth.ring.com/oauth/token"


@dataclass(frozen=True)
class Settings:
    source: str = "mock"  # mock | poll | webhook
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    hmac_key: Optional[str] = None
    device_id: Optional[str] = None
    poll_seconds: float = 3.0

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            source=e("RINGDOOR_SOURCE", "mock"),
            access_token=e("RING_ACCESS_TOKEN") or None,
            refresh_token=e("RING_REFRESH_TOKEN") or None,
            client_id=e("RING_CLIENT_ID") or None,
            client_secret=e("RING_CLIENT_SECRET") or None,
            hmac_key=e("RING_WEBHOOK_HMAC_KEY") or None,
            device_id=e("RINGDOOR_DEVICE_ID") or None,
            poll_seconds=float(e("RINGDOOR_POLL_SECONDS", "3")),
        )
