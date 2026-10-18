"""Turn a WAV of the visitor's voice into a caption line."""
from __future__ import annotations

from .mac import run_script


def transcribe_wav(wav: bytes) -> str:
    if len(wav) < 44:
        return ""
    return " ".join(run_script("transcribe.js", wav, ".wav", timeout=30).split())
