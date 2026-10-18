"""Alert pipeline. Stages turn a DoorEvent into zero or more Alerts.

RuleStage is the deterministic baseline (no AI, always works). Add richer stages later, e.g.:
  - CaptionStage: open a WHEP session on button_press, transcribe the visitor's audio, emit live captions
  - ContextStage: snapshot -> Bedrock vision description (no identification of people)
  - SignStage: hand/body landmarks -> sign text
and register them in `default_stages()`.
"""
from __future__ import annotations

import time
from typing import List, Optional, Protocol

from pydantic import BaseModel

from .events import DoorEvent


class Alert(BaseModel):
    id: str
    level: str  # visitor | motion | info
    headline: str
    detail: str = ""
    event_id: str
    created_ms: int


class Stage(Protocol):
    async def handle(self, event: DoorEvent) -> List[Alert]: ...


_SUBTYPE_TEXT = {
    "human": "A person is at your door",
    "package_delivery": "A package delivery is at your door",
    "vehicle": "A vehicle is near your door",
    "other_motion": "Motion at your door",
    "motion": "Motion at your door",
}


class RuleStage:
    async def handle(self, event: DoorEvent) -> List[Alert]:
        now = int(time.time() * 1000)
        if event.type == "button_press":
            return [Alert(id=f"a_{event.id}", level="visitor", headline="Someone rang your doorbell", detail="Check the door.", event_id=event.id, created_ms=now)]
        if event.type == "motion_detected":
            text = _SUBTYPE_TEXT.get(event.sub_type or "motion", "Motion at your door")
            return [Alert(id=f"a_{event.id}", level="motion", headline=text, event_id=event.id, created_ms=now)]
        return []


def default_stages() -> List[Stage]:
    return [RuleStage()]


async def run_stages(stages: List[Stage], event: DoorEvent) -> List[Alert]:
    alerts: List[Alert] = []
    for stage in stages:
        try:
            alerts.extend(await stage.handle(event))
        except Exception as exc:  # one failing stage must not drop the baseline alert
            print(f"[pipeline] {type(stage).__name__} failed: {exc}")
    return alerts
