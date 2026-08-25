"""Internationalisation par utilisateur.

Chaque utilisateur choisit sa langue avec /language ; elle est stockée dans
data/users.json et s'applique aux réponses que le bot LUI adresse.

Les traductions vivent dans data/locales/<code>.json (une clé = un texte).
Ajouter une langue = déposer un fichier et l'inscrire dans LANGS. Une clé
absente d'une locale retombe sur l'anglais, puis sur le français : une
traduction partielle reste donc utilisable.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT = "fr"
FALLBACKS = ("en", "fr")

LANGS = {
    "fr": "Français 🇫🇷",
    "en": "English 🇬🇧",
    "es": "Español 🇪🇸",
    "it": "Italiano 🇮🇹",
    "sv": "Svenska 🇸🇪",
    "fi": "Suomi 🇫🇮",
    "no": "Norsk 🇳🇴",
    "vi": "Tiếng Việt 🇻🇳",
}

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "data" / "locales"
_USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"

_catalogs: dict[str, dict[str, str]] = {}


def _catalog(lang: str) -> dict[str, str]:
    if lang not in _catalogs:
        path = _LOCALES_DIR / f"{lang}.json"
        try:
            with path.open(encoding="utf-8") as f:
                _catalogs[lang] = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            log.warning("Locale %s illisible (%s) : repli sur l'anglais", lang, exc)
            _catalogs[lang] = {}
    return _catalogs[lang]


def user_lang(user_id: int) -> str:
    try:
        with _USERS_FILE.open(encoding="utf-8") as f:
            lang = json.load(f).get(str(user_id), {}).get("lang", DEFAULT)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT
    return lang if lang in LANGS else DEFAULT


def set_user_lang(user_id: int, lang: str) -> None:
    try:
        with _USERS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault(str(user_id), {})["lang"] = lang
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def t(lang: str, key: str, **kwargs) -> str:
    """Texte localisé. Repli : langue demandée → anglais → français → clé."""
    text = None
    for candidate in (lang, *FALLBACKS):
        text = _catalog(candidate).get(key)
        if text is not None:
            break
    if text is None:
        return key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # Une locale mal formée ne doit jamais casser une réponse du bot
        log.warning("Substitution impossible pour « %s » en %s", key, lang)
        fallback = _catalog(DEFAULT).get(key, key)
        try:
            return fallback.format(**kwargs)
        except Exception:
            return fallback
