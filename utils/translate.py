"""Traduction automatique des contenus rédigés à la main (builds, maps).

Utilise Google Translate via deep-translator (gratuit, sans clé), avec un
cache disque : chaque texte n'est traduit qu'une fois par langue. En cas
d'échec (hors-ligne, service KO), le texte original est renvoyé tel quel.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from utils import i18n

log = logging.getLogger(__name__)

_CACHE_FILE = Path(__file__).resolve().parent.parent / "data" / "translations.json"
_GOOGLE_CODES = {"fr": "fr", "en": "en", "no": "no"}
MAX_CHARS = 4500  # limite Google ~5000 ; nos textes sont bien plus courts

_cache: dict[str, str] | None = None


def _load_cache() -> dict[str, str]:
    global _cache
    if _cache is None:
        try:
            with _CACHE_FILE.open(encoding="utf-8") as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=1)


def _translate_sync(text: str, lang: str) -> str:
    from deep_translator import GoogleTranslator

    return GoogleTranslator(source="auto", target=_GOOGLE_CODES.get(lang, lang)).translate(text)


async def tr(text: str | None, lang: str) -> str | None:
    """Traduit `text` vers `lang`. Langue par défaut ou échec → texte original."""
    if not text or lang == i18n.DEFAULT or len(text) > MAX_CHARS:
        return text

    cache = _load_cache()
    key = f"{lang}:{hashlib.sha1(text.encode('utf-8')).hexdigest()}"
    hit = cache.get(key)
    if hit is not None:
        return hit

    try:
        translated = await asyncio.to_thread(_translate_sync, text, lang)
    except Exception as exc:
        log.warning("Traduction vers %s impossible : %s", lang, exc)
        return text
    if not translated:
        return text

    cache[key] = translated
    try:
        _save_cache()
    except OSError as exc:
        log.warning("Cache de traduction non sauvegardé : %s", exc)
    return translated
