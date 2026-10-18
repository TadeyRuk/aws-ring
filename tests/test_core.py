import asyncio
import json

import httpx
import pytest

from ringdoor.config import Settings
from ringdoor.scene import sentence_from_labels
from ringdoor.events import normalize_history_item, normalize_webhook
from ringdoor.main import create_app
from ringdoor.sources import mock_webhook_body
from ringdoor.webhook import sign, verify_signature

KEY = "test-hmac-key"


def test_signature_roundtrip_and_tamper():
    raw = b'{"a": 1}'
    assert verify_signature(raw, sign(raw, KEY), KEY)
    assert not verify_signature(raw + b" ", sign(raw, KEY), KEY)  # signed over raw bytes
    assert not verify_signature(raw, None, KEY)
    assert not verify_signature(raw, "sha256=deadbeef", KEY)
    assert verify_signature(raw, None, None)  # disabled when no key configured


def test_normalize_webhook_motion_subtype():
    ev = normalize_webhook(mock_webhook_body("motion_detected", sub_type="package_delivery"))
    assert ev.type == "motion_detected" and ev.sub_type == "package_delivery"
    assert ev.device_id and ev.request_id


def test_normalize_history_maps_ding_and_motion():
    assert normalize_history_item({"id": "1", "attributes": {"event_type": "ding", "start": 5}}, "d").type == "button_press"
    m = normalize_history_item({"id": "2", "attributes": {"event_type": "motion.human", "start": 5}}, "d")
    assert (m.type, m.sub_type) == ("motion_detected", "human")


async def _client(settings):
    app = create_app(settings)
    return app, httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_webhook_end_to_end_dedupe_and_bad_signature():
    app, c = await _client(Settings(source="webhook", hmac_key=KEY))
    body = mock_webhook_body("button_press")
    raw = json.dumps(body).encode()
    hdr = {"X-Signature": sign(raw, KEY), "Content-Type": "application/json"}

    bad = await c.post("/webhook/ring", content=raw, headers={**hdr, "X-Signature": "sha256=00"})
    assert bad.status_code == 401

    ok = await c.post("/webhook/ring", content=raw, headers=hdr)
    assert ok.json()["status"] == "accepted"
    dup = await c.post("/webhook/ring", content=raw, headers=hdr)  # Ring retry, same request_id
    assert dup.json()["status"] == "duplicate"
    await asyncio.sleep(0.05)

    kinds = [m["kind"] for m in app.state.bus.history]
    assert kinds == ["event", "alert"]
    alert = app.state.bus.history[1]
    assert alert["level"] == "visitor" and "doorbell" in alert["headline"].lower()


H264_OFFER = "v=0\r\nm=video 9 UDP/TLS/RTP/SAVPF 102\r\na=recvonly\r\na=rtpmap:102 H264/90000\r\n"


class FakeRing:
    def __init__(self):
        self.offers = []
        self.closed = []

    async def list_devices(self, include="status,capabilities,location,configurations"):
        return [{"id": "dev-1", "attributes": {"name": "Playground Device"}}]

    async def open_whep(self, device_id, sdp_offer):
        self.offers.append((device_id, sdp_offer))
        return "v=0\r\na=sendonly\r\n", "https://api.amazonvision.com/v1/sessions/abc"

    async def close_whep(self, session_url):
        self.closed.append(session_url)


async def test_live_offer_forwards_h264_and_close_rejects_other_hosts():
    ring = FakeRing()
    app = create_app(Settings(source="mock", device_id="dev-9"), client=ring)
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")

    missing = await c.post("/api/live/offer", content=b"v=0\r\na=recvonly\r\na=rtpmap:96 VP8/90000\r\n")
    assert missing.status_code == 400

    ok = await c.post("/api/live/offer", content=H264_OFFER.encode())
    assert ok.status_code == 200
    body = ok.json()
    assert body["sdp"].startswith("v=0")
    assert ring.offers[0][0] == "dev-9"

    evil = await c.post("/api/live/close", json={"session_url": "https://evil.example/v1/sessions/abc"})
    assert evil.status_code == 400
    closed = await c.post("/api/live/close", json={"session_url": body["session_url"]})
    assert closed.json()["status"] == "closed"
    assert ring.closed == [body["session_url"]]
    page = await c.get("/")
    assert "preferH264" in page.text and "Door Interpreter" in page.text


def test_scene_sentence_names_the_door_and_not_the_person():
    assert sentence_from_labels([("John Smith", 0.99), ("package_delivery", 0.4)]) == "A package is at the door."
    assert "John" not in sentence_from_labels([("John Smith", 0.99), ("person", 0.2)])
    assert sentence_from_labels([("person", 0.8)]) == "A person is at the door."
    assert sentence_from_labels([("outdoor", 0.5), ("door", 0.3)]) == "The doorway is clear."
    assert sentence_from_labels([("keyboard", 0.9)]) == "Nothing distinct is at the door."


async def test_caption_and_scene_publish_on_the_alert_stream():
    seen = {}

    def describe(image: bytes) -> str:
        seen["image"] = image
        return "A package is at the door."

    def transcribe(wav: bytes) -> str:
        seen["wav"] = wav
        return "I have a package"

    app = create_app(Settings(source="mock"), describe=describe, transcribe=transcribe)
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    said = await c.post("/api/captions", content=b"RIFFxxxxWAVEfmt ")
    assert said.json()["text"] == "I have a package"
    shown = await c.post("/api/scene", content=b"\xff\xd8\xff not-a-real-jpeg")
    assert shown.json()["sentence"] == "A package is at the door."
    assert "John" not in shown.json()["sentence"]
    kinds = [m["kind"] for m in app.state.bus.history]
    assert kinds == ["caption", "scene"]


async def test_live_offer_needs_credentials():
    _, c = await _client(Settings(source="mock"))
    denied = await c.post("/api/live/offer", content=H264_OFFER.encode())
    assert denied.status_code == 503


async def test_dev_mock_disabled_in_webhook_mode_enabled_in_mock_mode():
    _, c = await _client(Settings(source="webhook"))
    assert (await c.post("/dev/mock/button_press")).status_code == 404
    app, c2 = await _client(Settings(source="mock"))
    assert (await c2.post("/dev/mock/motion_detected?sub_type=human")).status_code == 200
    assert app.state.bus.history[-1]["headline"] == "A person is at your door"
