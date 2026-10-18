"""One sentence about a door snapshot. Labels never become a person's name."""
from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from .mac import run_script

# Order is the priority. A package matters more than the fact that a person is holding it.
_LINES = (
    ("package", "A package is at the door."),
    ("parcel", "A package is at the door."),
    ("box", "A package is at the door."),
    ("vehicle", "A vehicle is near the door."),
    ("car", "A vehicle is near the door."),
    ("truck", "A vehicle is near the door."),
    ("dog", "An animal is at the door."),
    ("cat", "An animal is at the door."),
    ("animal", "An animal is at the door."),
    ("person", "A person is at the door."),
    ("people", "A person is at the door."),
    ("human", "A person is at the door."),
)


def sentence_from_labels(labels: Sequence[Tuple[str, float]], minimum: float = 0.15) -> str:
    ranked = [(name.lower().replace("_", " "), score) for name, score in labels if score >= minimum]
    ranked.sort(key=lambda item: item[1], reverse=True)
    blob = " ".join(name for name, _ in ranked)
    for key, line in _LINES:
        if re.search(rf"\b{re.escape(key)}\b", blob):
            return line
    if any(re.search(r"\b(door|doorway|porch|outdoor)\b", name) for name, _ in ranked):
        return "The doorway is clear."
    return "Nothing distinct is at the door."


def parse_labels(text: str) -> List[Tuple[str, float]]:
    labels: List[Tuple[str, float]] = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        name, score = line.split("\t", 1)
        try:
            labels.append((name.strip(), float(score)))
        except ValueError:
            continue
    return labels


def describe_image(image: bytes) -> str:
    """Run the on-device image classifier and return one fixed sentence."""
    text = run_script("describe.js", image, ".jpg", timeout=90)
    return sentence_from_labels(parse_labels(text))
