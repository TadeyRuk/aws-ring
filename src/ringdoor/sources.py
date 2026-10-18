"""Event sources. All feed the same EventBus path so the rest of the app doesn't care where events come from."""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, Optional

from .events import DoorEvent, normalize_history_item, normalize_webhook
from .ring_client import RingClient


def mock_webhook_body(kind: str = "button_press", device_id: str = "mock.ring.device.front-door", sub_type: Optional[str] = None) -> Dict[str, Any]:
    """Synthetic payload in the documented v1.1 envelope (button_press / motion_detected)."""
    ts = int(time.time() * 1000)
    attrs: Dict[str, Any] = {"source": device_id, "source_type": "devices", "timestamp": ts}
    if kind == "motion_detected":
        attrs["sub_type"] = sub_type or "human"
    return {
        "meta": {"version": "1.1", "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "request_id": str(uuid.uuid4()), "account_id": "mock-account"},
        "data": {
            "id": f"{device_id}_{'motion' if kind == 'motion_detected' else 'button_press'}_{ts}",
            "type": kind,
            "attributes": attrs,
            "relationships": {"devices": {"links": {"self": f"/v1/devices/{device_id}"}}},
        },
    }


def mock_event(kind: str = "button_press", sub_type: Optional[str] = None) -> DoorEvent:
    return normalize_webhook(mock_webhook_body(kind, sub_type=sub_type), source="mock")


async def poll_history(client: RingClient, device_id: str, interval: float, emit) -> None:
    """For Playground tokens: webhook URLs are set during partner onboarding, so poll event history instead.
    First pass only records what already exists (no replay of old events as new alerts)."""
    seen = set()
    primed = False
    while True:
        try:
            for item in await client.event_history(device_id):
                ev = normalize_history_item(item, device_id)
                if ev.id in seen:
                    continue
                seen.add(ev.id)
                if primed:
                    emit(ev)
            primed = True
        except Exception as exc:  # keep polling through transient errors / token expiry
            print(f"[poll] {type(exc).__name__}: {exc}")
        await asyncio.sleep(interval)
