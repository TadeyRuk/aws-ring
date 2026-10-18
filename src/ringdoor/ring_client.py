from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import API_BASE, TOKEN_URL, Settings


class TokenProvider:
    """Static Playground access token, or OAuth refresh flow (access ~4h, refresh ~30d)."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._token = settings.access_token
        self._expires_at = float("inf") if settings.access_token else 0.0

    async def get(self, http: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        s = self._s
        if not (s.refresh_token and s.client_id and s.client_secret):
            raise RuntimeError("No valid Ring credentials: set RING_ACCESS_TOKEN or the refresh-token trio")
        r = await http.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": s.refresh_token,
                "client_id": s.client_id,
                "client_secret": s.client_secret,
            },
        )
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._expires_at = time.time() + float(body.get("expires_in", 3600))
        return self._token


class RingClient:
    """Thin async wrapper over the Ring Partner API (JSON:API). Server-to-server only (CORS blocks browsers)."""

    def __init__(self, settings: Settings, http: Optional[httpx.AsyncClient] = None) -> None:
        self._http = http or httpx.AsyncClient(timeout=15)
        self._tokens = TokenProvider(settings)

    async def _headers(self, **extra: str) -> Dict[str, str]:
        return {"Authorization": f"Bearer {await self._tokens.get(self._http)}", **extra}

    async def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        r = await self._http.get(API_BASE + path, headers=await self._headers(), params=params or None)
        r.raise_for_status()
        return r.json()

    async def list_devices(self, include: str = "status,capabilities,location,configurations") -> List[Dict[str, Any]]:
        return (await self._get("/v1/devices", include=include)).get("data", [])

    async def event_history(self, device_id: str, event_types: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"event_types": event_types} if event_types else {}
        return (await self._get(f"/v1/history/devices/{device_id}/events", **params)).get("data", [])

    async def open_whep(self, device_id: str, sdp_offer: str) -> Tuple[str, Optional[str]]:
        """WHEP session. All tracks must be recvonly; sessions cap at 30s (battery) / 60s (line-powered)."""
        r = await self._http.post(
            f"{API_BASE}/v1/devices/{device_id}/media/streaming/whep/sessions",
            headers=await self._headers(**{"Content-Type": "application/sdp"}),
            content=sdp_offer,
        )
        r.raise_for_status()
        return r.text, r.headers.get("Location")

    async def close_whep(self, session_url: str) -> None:
        await self._http.delete(session_url, headers=await self._headers())

    async def download_snapshot(self, device_id: str, start_ms: Optional[int] = None) -> bytes:
        """Latest JPEG in the last day. Follows the 303 to the pre-signed image URL."""
        now = int(time.time() * 1000)
        payload = {
            "type": "latest_in_range",
            "start_timestamp": start_ms if start_ms is not None else now - 24 * 60 * 60 * 1000,
            "end_timestamp": now,
            "image_options": {"format": "jpeg"},
        }
        r = await self._http.post(
            f"{API_BASE}/v1/devices/{device_id}/media/image/download",
            headers=await self._headers(**{"Content-Type": "application/json"}),
            json=payload,
            follow_redirects=True,
        )
        r.raise_for_status()
        if not r.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError("Ring did not return an image")
        return r.content

    async def play_chime(self, device_id: str, audio_ref: str) -> Dict[str, Any]:
        """Plays a customizable-slot sound on a *chime* (needs Chime Controls). Not a doorbell speaker."""
        r = await self._http.post(
            f"{API_BASE}/v1/devices/{device_id}/media/audio/playback",
            headers=await self._headers(**{"Content-Type": "application/json"}),
            json={"data": {"type": "audio", "attributes": {"audio_ref": audio_ref}}},
        )
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self._http.aclose()
