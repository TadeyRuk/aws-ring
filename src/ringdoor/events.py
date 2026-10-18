from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel


class DoorEvent(BaseModel):
    """Normalized Ring event. `type` is button_press | motion_detected | other."""

    id: str
    type: str
    sub_type: Optional[str] = None
    device_id: Optional[str] = None
    ts_ms: int
    request_id: Optional[str] = None
    source: str  # webhook | poll | mock
    raw: Dict[str, Any] = {}


def normalize_webhook(body: Dict[str, Any], source: str = "webhook") -> DoorEvent:
    """Ring webhook envelope v1.1: {meta:{request_id,...}, data:{id,type,attributes:{source,timestamp,sub_type}}}."""
    meta = body.get("meta", {})
    data = body.get("data", {})
    attrs = data.get("attributes", {})
    return DoorEvent(
        id=data.get("id") or f"evt_{int(time.time() * 1000)}",
        type=data.get("type", "other"),
        sub_type=attrs.get("sub_type"),
        device_id=attrs.get("source"),
        ts_ms=int(attrs.get("timestamp") or time.time() * 1000),
        request_id=meta.get("request_id"),
        source=source,
        raw=body,
    )


def normalize_history_item(item: Dict[str, Any], device_id: str) -> DoorEvent:
    """Event-history item. Shape is not fully documented; the starter reads attributes.event_type
    (e.g. 'ding', 'motion.human') and attributes.start. Verify against a real response."""
    attrs = item.get("attributes", {})
    raw_type = str(attrs.get("event_type", "other"))
    if raw_type == "ding" or raw_type == "button_press":
        etype, sub = "button_press", None
    elif raw_type.startswith("motion"):
        etype, sub = "motion_detected", (raw_type.split(".", 1)[1] if "." in raw_type else "motion")
    else:
        etype, sub = "other", raw_type
    return DoorEvent(
        id=str(item.get("id") or f"{device_id}_{raw_type}_{attrs.get('start')}"),
        type=etype,
        sub_type=sub,
        device_id=device_id,
        ts_ms=_to_ms(attrs.get("start")),
        source="poll",
        raw=item,
    )


def _to_ms(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        from datetime import datetime

        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            pass
    return int(time.time() * 1000)


class EventBus:
    """In-memory fan-out with replay and idempotency. Messages are dicts: {kind: event|alert, ...}."""

    def __init__(self, max_history: int = 200) -> None:
        self.history: List[Dict[str, Any]] = []
        self._subs: Set["asyncio.Queue[Dict[str, Any]]"] = set()
        self._seen: Set[str] = set()
        self._max = max_history

    def is_duplicate(self, key: Optional[str]) -> bool:
        """Ring retries deliveries; request_id (or event id) makes handling idempotent."""
        if not key:
            return False
        if key in self._seen:
            return True
        self._seen.add(key)
        if len(self._seen) > 5000:
            self._seen = set(list(self._seen)[-2500:])
        return False

    def publish(self, message: Dict[str, Any]) -> None:
        self.history.append(message)
        del self.history[: -self._max]
        for q in list(self._subs):
            q.put_nowait(message)

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._subs.add(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subs.discard(q)
