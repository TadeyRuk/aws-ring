#!/usr/bin/env python3
"""Spike: find out what a Ring Playground token actually gives us. Run first, paste output back.

  .venv/bin/python scripts/ring_probe.py --token "eyJ..."

Answers: does the token see a device (real or synthetic)? Is it a doorbell or a camera? Is video e2e-encrypted
(unreadable)? Is it battery (30s stream cap) or line-powered (60s)? Are there recent events? Can we get a
WHEP session (needs a WebRTC client, so this only prints the call to make)?
"""
import argparse
import json
import sys

import httpx

API = "https://api.amazonvision.com"


def clean_token(raw: str) -> str:
    token = raw.strip().strip('"').strip("'")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def describe_token(token: str) -> str:
    parts = token.split(".")
    kind = "jwt" if len(parts) == 3 and all(parts) else "not a jwt"
    return f"length={len(token)} shape={kind}"


def get(token, path, **params):
    r = httpx.get(API + path, headers={"Authorization": f"Bearer {token}"}, params=params or None, timeout=20)
    print(f"\nGET {path} -> {r.status_code}")
    if r.status_code == 401:
        www = r.headers.get("www-authenticate", "")
        if www:
            print(f"WWW-Authenticate: {www}")
    try:
        body = r.json()
    except ValueError:
        body = {"_text": r.text[:500]}
    if body != {"_text": ""}:
        print(json.dumps(body, indent=2)[:6000])
    return r.status_code, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--device-id")
    a = ap.parse_args()
    token = clean_token(a.token)
    if not token:
        sys.exit("Empty token.")
    print(f"Token {describe_token(token)}")

    code, body = get(token, "/v1/devices", include="status,capabilities,location,configurations")
    if code == 401:
        sys.exit(
            "Ring rejected this token. Generate a new one at "
            "https://developer.amazon.com/ring/console/playground (they last ~30 min), "
            "copy only the access token, and pass it in quotes."
        )
    if code != 200:
        sys.exit(f"Unexpected status {code}.")
    devices = body.get("data", [])
    print(f"\n== {len(devices)} device(s) ==")
    if not devices:
        sys.exit("No devices visible to this token: Playground may need a linked Ring account/device.")
    dev = a.device_id or devices[0]["id"]
    print(f"Using device: {dev}")
    get(token, f"/v1/history/devices/{dev}/events")
    print(
        "\nNext (needs a WebRTC client): POST "
        f"{API}/v1/devices/{dev}/media/streaming/whep/sessions with Content-Type: application/sdp, "
        "all tracks recvonly (audio optional). Streams last 30s (battery) / 60s (line-powered)."
    )


if __name__ == "__main__":
    main()
