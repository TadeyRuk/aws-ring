"""On-device vision and speech through macOS. osascript is the runtime; Swift is not."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def run_script(name: str, payload: bytes, suffix: str, timeout: int) -> str:
    if not payload:
        raise ValueError("empty input")
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        handle.write(payload)
        handle.close()
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", str(_SCRIPTS / name), handle.name],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    finally:
        os.unlink(handle.name)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "osascript failed"
        raise RuntimeError(detail)
    text = proc.stdout.strip()
    if text.startswith("ERR"):
        raise RuntimeError(text[4:].strip() or "native tool failed")
    return text
