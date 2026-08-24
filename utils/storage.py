"""Petit stockage JSON sur disque pour les maps et les builds."""

from __future__ import annotations

import json
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_lock = threading.Lock()


def load(name: str) -> dict:
    """Charge data/<name>.json ; retourne {} si absent ou invalide."""
    path = DATA_DIR / f"{name}.json"
    with _lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


def save(name: str, data: dict) -> None:
    """Écrit data/<name>.json de manière atomique."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    tmp = path.with_suffix(".json.tmp")
    with _lock:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
