"""Récupération de l'arbitration en cours / à venir et notation F → S.

Sources :
 - Arbitration en cours : https://api.warframestat.us/pc/arbitration (API WFCD)
 - Arbitrations à venir : https://browser.wf/arbys.json (prédictions communautaires,
   best-effort : si l'endpoint est indisponible ou change de format, le tracker
   n'affiche que l'arbitration en cours)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

CURRENT_URL = "https://api.warframestat.us/pc/arbitration"
UPCOMING_URL = "https://browser.wf/arbys.json"
TIMEOUT = aiohttp.ClientTimeout(total=15)

log = logging.getLogger(__name__)

TIER_ORDER = ["S", "A", "B", "C", "D", "F"]
TIER_EMOJI = {"S": "🟡", "A": "🟢", "B": "🔵", "C": "⚪", "D": "🟠", "F": "🔴"}

# Nom FR des modes de mission (clés = valeurs renvoyées par l'API, en anglais)
TYPE_FR = {
    "defense": "Défense",
    "survival": "Survie",
    "interception": "Interception",
    "excavation": "Excavation",
    "defection": "Défection",
    "infested salvage": "Sauvetage Infesté",
    "disruption": "Perturbation",
    "assault": "Assaut",
    "free roam": "Paysage ouvert",
    "mirror defense": "Défense Miroir",
    "alchemy": "Alchimie",
    "skirmish": "Escarmouche",
}

# Note par défaut selon le mode de mission (consensus communautaire, modifiable
# par serveur avec /tier-set)
TYPE_TIER = {
    "defense": "A",
    "survival": "A",
    "disruption": "A",
    "excavation": "B",
    "interception": "B",
    "mirror defense": "B",
    "assault": "C",
    "alchemy": "C",
    "infested salvage": "D",
    "defection": "F",
    "free roam": "F",
    "skirmish": "F",
}

# Nœuds emblématiques : la note du nœud prime sur celle du mode
NODE_TIER = {
    "casta (ceres)": "S",
    "hydron (sedna)": "S",
    "helene (saturn)": "S",
    "ophelia (uranus)": "S",
    "cinxia (ceres)": "A",
    "odin (mercury)": "B",
}


@dataclass
class Arbitration:
    node: str
    mission_type: str        # nom FR affichable
    type_key: str            # clé anglaise normalisée (pour la notation)
    enemy: str
    expiry: datetime | None = None
    activation: datetime | None = None


def rate(arby: Arbitration, guild_overrides: dict[str, str] | None = None) -> str:
    """Note F → S : override serveur > nœud connu > mode de mission."""
    node_key = arby.node.lower()
    if guild_overrides:
        tier = guild_overrides.get(node_key)
        if tier in TIER_ORDER:
            return tier
    return NODE_TIER.get(node_key) or TYPE_TIER.get(arby.type_key, "C")


def _parse_iso(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_epoch(value) -> datetime | None:
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return None
    if ts > 1e12:  # millisecondes
        ts /= 1000
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def _normalize_type(value: str) -> tuple[str, str]:
    key = value.strip().lower()
    return TYPE_FR.get(key, value.strip()), key


async def fetch_current(session: aiohttp.ClientSession) -> Arbitration | None:
    """Arbitration en cours via warframestat.us. None si indisponible."""
    try:
        async with session.get(CURRENT_URL, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json()
    except Exception as exc:  # réseau, JSON, 5xx…
        log.warning("Arbitration en cours indisponible : %s", exc)
        return None

    node = data.get("node") or data.get("nodeKey")
    if not node:
        return None
    type_fr, type_key = _normalize_type(str(data.get("type") or data.get("typeKey") or "?"))
    return Arbitration(
        node=str(node),
        mission_type=type_fr,
        type_key=type_key,
        enemy=str(data.get("enemy") or "?"),
        expiry=_parse_iso(data.get("expiry")),
        activation=_parse_iso(data.get("activation")),
    )


def _upcoming_entry(item: dict) -> Arbitration | None:
    """Convertit une entrée de prédiction, tolérant plusieurs noms de champs."""
    node = item.get("node") or item.get("nodeKey") or item.get("name")
    if not node:
        return None
    type_raw = item.get("type") or item.get("typeKey") or item.get("mission_type") or "?"
    type_fr, type_key = _normalize_type(str(type_raw))
    start = (
        _parse_iso(item.get("activation") or item.get("start") or item.get("time"))
        or _parse_epoch(item.get("activation") or item.get("start") or item.get("time"))
    )
    return Arbitration(
        node=str(node),
        mission_type=type_fr,
        type_key=type_key,
        enemy=str(item.get("enemy") or ""),
        activation=start,
    )


async def fetch_upcoming(session: aiohttp.ClientSession, limit: int = 6) -> list[Arbitration]:
    """Prochaines arbitrations (best-effort). Liste vide si la source est KO."""
    try:
        async with session.get(UPCOMING_URL, timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    except Exception as exc:
        log.warning("Prédictions d'arbitration indisponibles : %s", exc)
        return []

    if isinstance(data, dict):
        for key in ("upcoming", "arbitrations", "data", "predictions"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        log.warning("Format de prédictions inattendu (%s)", type(data).__name__)
        return []

    now = datetime.now(timezone.utc)
    result: list[Arbitration] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        arby = _upcoming_entry(item)
        if arby is None:
            continue
        if arby.activation and arby.activation < now:
            continue
        result.append(arby)
        if len(result) >= limit:
            break
    return result
