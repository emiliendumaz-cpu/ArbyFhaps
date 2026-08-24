"""Stockage JSON par serveur (maps/compos et builds personnalisés)."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GUILDS_DIR = DATA_DIR / "guilds"


def _guild_file(guild_id: int) -> Path:
    GUILDS_DIR.mkdir(parents=True, exist_ok=True)
    return GUILDS_DIR / f"{guild_id}.json"


def load_guild(guild_id: int) -> dict:
    path = _guild_file(guild_id)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {"maps": {}, "builds": []}


def save_guild(guild_id: int, data: dict) -> None:
    with _guild_file(guild_id).open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def all_guild_ids() -> list[int]:
    if not GUILDS_DIR.exists():
        return []
    return [int(p.stem) for p in GUILDS_DIR.glob("*.json") if p.stem.isdigit()]


def load_default_builds() -> list[dict]:
    path = DATA_DIR / "builds.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)
