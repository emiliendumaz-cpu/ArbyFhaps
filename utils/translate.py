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


# Fragments typiques d'une page d'erreur renvoyée à la place d'une traduction
_ERROR_MARKERS = ("that's an error", "that’s an error", "error 500", "please try again later",
                  "mymemory warning")

# Codes de langue de MyMemory (traducteur de secours quand Google refuse)
_MYMEMORY_CODES = {"fr": "fr-FR", "en": "en-GB", "no": "nb-NO"}  # nb-NO = bokmål
# MyMemory refuse les requêtes de 500 caractères et plus ; marge pour l'encodage UTF-8
_MYMEMORY_MAX = 450


def _looks_broken(original: str, translated: str) -> bool:
    low = translated.lower()
    if any(marker in low for marker in _ERROR_MARKERS):
        return True
    # Longueur aberrante : une vraie traduction reste du même ordre de grandeur
    if len(original) >= 40 and not (len(original) // 5 <= len(translated) <= len(original) * 3):
        return True
    return False


def _load_cache() -> dict[str, str]:
    global _cache
    if _cache is None:
        try:
            with _CACHE_FILE.open(encoding="utf-8") as f:
                _cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _cache = {}
        # Auto-nettoyage : purge les pages d'erreur mises en cache par erreur
        broken = [k for k, v in _cache.items()
                  if any(m in str(v).lower() for m in _ERROR_MARKERS)]
        if broken:
            for k in broken:
                del _cache[k]
            log.warning("Cache de traduction : %d entrées corrompues purgées", len(broken))
            try:
                _save_cache()
            except OSError:
                pass
    return _cache


def _save_cache() -> None:
    if _cache is None:
        return
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _CACHE_FILE.open("w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=1)


def _iter_translators(lang: str):
    """Chaîne de traducteurs : Google (rapide) puis MyMemory (secours sans clé).

    Google bloque parfois son endpoint gratuit (« Error 500 ») selon l'IP ;
    MyMemory est une API officielle au quota journalier modeste — largement
    suffisant grâce au cache. Chaque élément : (nom, traducteur, taille max
    d'une requête ou None). Chaque construction est protégée : l'échec de
    l'une ne prive pas de la suivante.
    """
    try:
        from deep_translator import GoogleTranslator

        yield "Google", GoogleTranslator(source="auto", target=_GOOGLE_CODES.get(lang, lang)), None
    except Exception as exc:
        log.debug("Google indisponible : %s", exc)
    try:
        from deep_translator import MyMemoryTranslator

        # Les textes des admins sont rédigés en français
        yield ("MyMemory",
               MyMemoryTranslator(source="fr-FR", target=_MYMEMORY_CODES.get(lang, lang)),
               _MYMEMORY_MAX)
    except Exception as exc:
        log.debug("MyMemory indisponible : %s", exc)


def _split_line(line: str, limit: int | None) -> list[str]:
    """Découpe une ligne trop longue pour un traducteur, de préférence aux
    frontières de phrases puis de mots. Sans limite (ou ligne assez courte),
    la ligne est renvoyée telle quelle."""
    if limit is None or len(line) <= limit:
        return [line]
    chunks: list[str] = []
    rest = line
    while len(rest) > limit:
        cut = -1
        for sep in (". ", "! ", "? ", "; ", ", ", " "):
            cut = rest.rfind(sep, 1, limit)
            if cut != -1:
                cut += len(sep)
                break
        if cut <= 0:
            cut = limit
        if rest[:cut].strip():
            chunks.append(rest[:cut].strip())
        rest = rest[cut:]
    if rest.strip():
        chunks.append(rest.strip())
    return chunks


def _translate_sync(text: str, lang: str) -> str:
    """Traduit ligne par ligne : requêtes courtes et markdown préservé.

    Chaque traducteur de la chaîne est essayé en entier ; une réponse suspecte
    (page d'erreur, longueur aberrante) fait passer au suivant. Si tous
    échouent, l'appelant affiche le texte original et ne met rien en cache.
    """
    last_error: Exception | None = None
    for name, translator, limit in _iter_translators(lang):
        try:
            out: list[str] = []
            for line in text.split("\n"):
                if not line.strip():
                    out.append(line)
                    continue
                parts: list[str] = []
                for piece in _split_line(line, limit):
                    translated = translator.translate(piece)
                    if not translated or not isinstance(translated, str):
                        parts.append(piece)
                        continue
                    if _looks_broken(piece, translated):
                        raise ValueError(f"réponse suspecte ({name}) : {translated[:80]!r}")
                    parts.append(translated)
                out.append(parts[0] if len(parts) == 1 else " ".join(parts))
            if name != "Google":
                log.info("Traduction assurée par %s (Google indisponible)", name)
            return "\n".join(out)
        except Exception as exc:
            last_error = exc
            log.warning("Traducteur %s en échec : %s", name, exc)
    raise last_error if last_error else RuntimeError("aucun traducteur disponible")


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
