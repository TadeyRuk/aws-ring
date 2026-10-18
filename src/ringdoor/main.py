from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from .captions import transcribe_wav
from .config import Settings
from .events import DoorEvent, EventBus, normalize_webhook
from .live import allowed_session_url, offer_error
from .scene import describe_image
from .pipeline import Stage, default_stages, run_stages
from .ring_client import RingClient
from .sources import mock_event, poll_history
from .webhook import verify_signature

STATIC = Path(__file__).parent / "static"


class CloseLive(BaseModel):
    session_url: str


def create_app(
    settings: Optional[Settings] = None,
    stages: Optional[List[Stage]] = None,
    client: Optional[RingClient] = None,
    describe=describe_image,
    transcribe=transcribe_wav,
) -> FastAPI:
    settings = settings or Settings.from_env()
    stages = stages if stages is not None else default_stages()
    bus = EventBus()
    owns_client = client is None
    if client is None and (settings.access_token or settings.refresh_token):
        client = RingClient(settings)
    tasks: List["asyncio.Task[None]"] = []

    async def ingest(ev: DoorEvent) -> None:
        bus.publish({"kind": "event", **ev.model_dump(exclude={"raw"})})
        for alert in await run_stages(stages, ev):
            bus.publish({"kind": "alert", **alert.model_dump()})

    def emit_sync(ev: DoorEvent) -> None:
        tasks.append(asyncio.ensure_future(ingest(ev)))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.source == "poll":
            if not (client and settings.device_id):
                raise RuntimeError("RINGDOOR_SOURCE=poll needs a Ring token and RINGDOOR_DEVICE_ID")
            tasks.append(asyncio.create_task(poll_history(client, settings.device_id, settings.poll_seconds, emit_sync)))
        yield
        for t in tasks:
            t.cancel()
        if owns_client and client:
            await client.aclose()

    app = FastAPI(title="ringdoor", lifespan=lifespan)
    app.state.bus = bus

    @app.post("/webhook/ring")
    async def ring_webhook(request: Request):
        raw = await request.body()
        if not verify_signature(raw, request.headers.get("X-Signature"), settings.hmac_key):
            return JSONResponse({"error": "bad signature"}, status_code=401)
        try:
            body = json.loads(raw)
        except ValueError:
            return JSONResponse({"error": "invalid json"}, status_code=400)
        ev = normalize_webhook(body)
        if bus.is_duplicate(ev.request_id or ev.id):
            return {"status": "duplicate"}
        # Ring requires a 200 within 5s; do the work after responding.
        asyncio.ensure_future(ingest(ev))
        return {"status": "accepted"}

    @app.get("/api/recent")
    async def recent():
        return bus.history

    @app.get("/stream")
    async def stream():
        q = bus.subscribe()

        async def gen():
            try:
                for m in bus.history:
                    yield f"data: {json.dumps(m)}\n\n"
                while True:
                    try:
                        m = await asyncio.wait_for(q.get(), timeout=20)
                        yield f"data: {json.dumps(m)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                bus.unsubscribe(q)

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    async def device_id() -> str:
        if settings.device_id:
            return settings.device_id
        devices = await client.list_devices()
        if not devices:
            raise HTTPException(404, "No Ring devices on this token")
        return devices[0]["id"]

    @app.post("/api/live/offer")
    async def live_offer(request: Request):
        if not client:
            raise HTTPException(503, "No Ring credentials configured")
        sdp = (await request.body()).decode("utf-8", errors="replace")
        problem = offer_error(sdp)
        if problem:
            raise HTTPException(400, problem)
        try:
            answer, session_url = await client.open_whep(await device_id(), sdp)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, exc.response.text[:300] or "Ring rejected the live view")
        return {"sdp": answer, "session_url": session_url}

    @app.post("/api/live/close")
    async def live_close(body: CloseLive):
        if not client:
            raise HTTPException(503, "No Ring credentials configured")
        if not allowed_session_url(body.session_url):
            raise HTTPException(400, "Session URL is not a Ring media session")
        await client.close_whep(body.session_url)
        return {"status": "closed"}

    @app.post("/api/captions")
    async def captions(request: Request):
        wav = await request.body()
        try:
            text = await asyncio.to_thread(transcribe, wav)
        except Exception as exc:
            raise HTTPException(502, str(exc))
        if text:
            bus.publish({"kind": "caption", "text": text})
        return {"text": text}

    @app.post("/api/scene")
    async def scene(request: Request):
        image = await request.body()
        if not image:
            raise HTTPException(400, "Expected an image body")
        try:
            sentence = await asyncio.to_thread(describe, image)
        except Exception as exc:
            raise HTTPException(502, str(exc))
        bus.publish({"kind": "scene", "text": sentence})
        return {"sentence": sentence}

    @app.post("/api/scene/ring")
    async def scene_ring():
        if not client:
            raise HTTPException(503, "No Ring credentials configured")
        try:
            image = await client.download_snapshot(await device_id())
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, exc.response.text[:300] or "No snapshot")
        try:
            sentence = await asyncio.to_thread(describe, image)
        except Exception as exc:
            raise HTTPException(502, str(exc))
        bus.publish({"kind": "scene", "text": sentence})
        return {"sentence": sentence}

    @app.get("/api/devices")
    async def devices():
        if not client:
            raise HTTPException(503, "No Ring credentials configured")
        return await client.list_devices()

    if settings.source != "webhook":
        @app.post("/dev/mock/{kind}")
        async def dev_mock(kind: str, sub_type: Optional[str] = None):
            if kind not in ("button_press", "motion_detected"):
                raise HTTPException(400, "kind must be button_press or motion_detected")
            await ingest(mock_event(kind, sub_type))
            return {"status": "ok"}

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    return app


def app_factory() -> FastAPI:  # uvicorn --factory ringdoor.main:app_factory
    return create_app()
