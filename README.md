# Ring

Track repo for the Amazon Developer Hackathon. This folder is the whole project: rules, sponsor context, the research prompt, and the research report. It does not depend on any other local folder.

- **Hackathon:** Build, Ship, Shape: Amazon Developer Hackathon
- **Deadline:** 23 Oct 2026, 12:00 PM PT
- **Track:** A new or extended app on Ring APIs, SDKs, simulators, or devices. Sponsor themes include access control, business systems, home automation, accessibility, and caretaking. Facial recognition and license-plate reading are out.

## Build

**Door Interpreter** — a deaf or hard-of-hearing resident reads the door. A ring flashes a high-contrast alert, the live picture plays, the visitor's words become a caption, and one sentence says what is there. The sentence is chosen from a fixed list, so nobody is identified.

The research report recommended SignSync. The Ring docs and the Playground device changed that: streams are receive-only, this doorbell speaks H264 only, and it cannot talk back. Sign recognition is not in this build.

## Docs

| File | What it is |
|---|---|
| [HACKATHON.md](HACKATHON.md) | Full hackathon rules and dates, copied so this repo stands alone |
| [ORG.md](ORG.md) | Amazon, AWS, and device-team goals, copied so this repo stands alone |
| [PROMPT.md](PROMPT.md) | Deep-research prompt for this track |
| [SignSync-AI-Deep-Research-Report.md](SignSync-AI-Deep-Research-Report.md) | Research report and the three pitches |

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # optional: RING_ACCESS_TOKEN from the Playground
.venv/bin/python -m pytest -q
sh scripts/demo.sh              # http://localhost:8000
```

Press **Simulate: Doorbell**. With a Playground token in `.env`, **Watch the door** opens the live view. The offer must be receive-only H264; a VP8 offer gets a 500 from Ring. **What is there** turns a snapshot into one sentence. Captions and that sentence use macOS speech and vision.

`src/ringdoor/` is the FastAPI service. Events share one path: `mock` (no Ring needed), `poll` (Playground token), `webhook` (HMAC-verified, idempotent).

```bash
.venv/bin/python scripts/ring_probe.py --token "<playground token>"
```

**Verified against Ring (2026-10-18):** WHEP, `recvonly`, H264, max 30 s (battery) / 60 s (line-powered). No talkback. Audio playback is for chimes. Webhooks use `X-Signature: sha256=<hex HMAC of raw body>`, must return 200 in 5 s, and the URL is set during partner onboarding. The Playground device is an online Doorbell Pro with an empty event history. Submission copy and the friction log are in [SUBMISSION.md](SUBMISSION.md).
