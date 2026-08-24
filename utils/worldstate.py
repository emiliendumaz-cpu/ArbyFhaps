"""Récupération de l'arbitration en cours / à venir et notation F → S.

Sources, par ordre d'essai :
 - warframestat.us : arbitration en cours (renvoie parfois des données non
   résolues type « SolNode000 / Unknown » → filtrées comme indisponibles)
 - semlar (10o.io) et browser.wf : planning des arbitrations (en cours + à
   venir). Best-effort : chaque source est tolérée en échec, la commande
   /sources permet de diagnostiquer depuis la machine qui héberge le bot.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

CURRENT_URL = "https://api.warframestat.us/pc/arbitration"
SCHEDULE_URLS = [
    ("semlar (10o.io)", "https://10o.io/arbitrations.json"),
    ("browser.wf", "https://browser.wf/arbys.json"),
]
DIAGNOSTIC_URLS = [("warframestat.us", CURRENT_URL)] + SCHEDULE_URLS
TIMEOUT = aiohttp.ClientTimeout(total=15)

log = logging.getLogger(__name__)

TIER_ORDER = ["S", "A", "B", "C", "D", "F"]
TIER_EMOJI = {"S": "🟡", "A": "🟢", "B": "🔵", "C": "⚪", "D": "🟠", "F": "🔴"}

# Nom FR des modes de mission (clés = valeurs renvoyées par les API, en anglais)
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
    "dark sector defense": "Défense (Secteur Obscur)",
    "dark sector survival": "Survie (Secteur Obscur)",
}

# Note par défaut selon le mode de mission (consensus communautaire, modifiable
# par serveur avec /tier-set)
TYPE_TIER = {
    "defense": "A",
    "dark sector defense": "A",
    "survival": "A",
    "dark sector survival": "A",
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
    "seimeni (ceres)": "S",
    "cinxia (ceres)": "A",
    "odin (mercury)": "B",
}

_RAW_SOLNODE_RE = re.compile(r"^SolNode\d+$", re.IGNORECASE)


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


def _parse_time(value) -> datetime | None:
    """Accepte ISO 8601 ou epoch (secondes/millisecondes)."""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
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


def _is_valid(arby: Arbitration) -> bool:
    """Écarte les réponses non résolues (SolNode000 / Unknown / Tenno)."""
    if _RAW_SOLNODE_RE.match(arby.node.strip()):
        return False
    if arby.type_key in ("unknown", "?", ""):
        return False
    if arby.enemy.strip().lower() == "tenno":
        return False
    return True


async def _get_json(session: aiohttp.ClientSession, url: str):
    async with session.get(url, timeout=TIMEOUT) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def fetch_current(session: aiohttp.ClientSession) -> Arbitration | None:
    """Arbitration en cours via warframestat.us ; None si indisponible/invalide."""
    try:
        data = await _get_json(session, CURRENT_URL)
    except Exception as exc:
        log.warning("warframestat.us indisponible : %s", exc)
        return None
    if not isinstance(data, dict):
        return None

    node = data.get("node") or data.get("nodeKey")
    if not node:
        return None
    type_fr, type_key = _normalize_type(str(data.get("type") or data.get("typeKey") or "?"))
    arby = Arbitration(
        node=str(node),
        mission_type=type_fr,
        type_key=type_key,
        enemy=str(data.get("enemy") or "?"),
        expiry=_parse_time(data.get("expiry")),
        activation=_parse_time(data.get("activation")),
    )
    if not _is_valid(arby):
        log.warning("warframestat.us a renvoyé une arbitration non résolue (%s)", arby.node)
        return None
    return arby


def _schedule_entry(item: dict) -> Arbitration | None:
    """Convertit une entrée de planning, tolérant plusieurs formats.

    Formats gérés :
     - semlar : {"start": …, "end": …, "solnode": "SolNode123",
                 "solnodedata": {"name"/"node", "planet", "enemy", "type", "tile"}}
     - générique : {"node"/"name", "type"/"mission_type", "activation"/"start"/"time"}
    """
    nested = item.get("solnodedata") if isinstance(item.get("solnodedata"), dict) else {}

    node = nested.get("node") or item.get("node") or item.get("nodeKey")
    if not node:
        name = nested.get("name") or item.get("name")
        planet = nested.get("planet") or item.get("planet")
        if name and planet:
            node = f"{name} ({planet})"
        else:
            node = name
    if not node or _RAW_SOLNODE_RE.match(str(node).strip()):
        return None

    type_raw = (nested.get("type") or item.get("type") or item.get("typeKey")
                or item.get("mission_type") or "?")
    type_fr, type_key = _normalize_type(str(type_raw))
    start = _parse_time(item.get("activation") or item.get("start") or item.get("time"))
    end = _parse_time(item.get("expiry") or item.get("end"))
    return Arbitration(
        node=str(node),
        mission_type=type_fr,
        type_key=type_key,
        enemy=str(nested.get("enemy") or item.get("enemy") or ""),
        activation=start,
        expiry=end,
    )


async def fetch_schedule(session: aiohttp.ClientSession, limit: int = 6) -> tuple[Arbitration | None, list[Arbitration]]:
    """Planning best-effort : (en cours d'après le planning, prochaines).

    Essaie chaque source de SCHEDULE_URLS ; renvoie (None, []) si tout est KO.
    """
    data = None
    for name, url in SCHEDULE_URLS:
        try:
            data = await _get_json(session, url)
            break
        except Exception as exc:
            log.warning("Planning %s indisponible : %s", name, exc)
    if data is None:
        return None, []

    if isinstance(data, dict):
        for key in ("upcoming", "arbitrations", "data", "predictions"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        log.warning("Format de planning inattendu (%s)", type(data).__name__)
        return None, []

    now = datetime.now(timezone.utc)
    current: Arbitration | None = None
    upcoming: list[Arbitration] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        arby = _schedule_entry(item)
        if arby is None:
            continue
        started = arby.activation is None or arby.activation <= now
        ended = arby.expiry is not None and arby.expiry <= now
        if ended:
            continue
        if started:
            current = arby  # la dernière entrée déjà commencée et non finie
        else:
            upcoming.append(arby)
            if len(upcoming) >= limit:
                break
    upcoming.sort(key=lambda a: a.activation or now)
    return current, upcoming


async def probe_sources(session: aiohttp.ClientSession) -> list[tuple[str, str, str]]:
    """Diagnostic /sources : (nom, url, résultat court) pour chaque source."""
    results = []
    for name, url in DIAGNOSTIC_URLS:
        try:
            async with session.get(url, timeout=TIMEOUT) as resp:
                body = (await resp.text())[:180].replace("\n", " ")
                results.append((name, url, f"HTTP {resp.status} — {body}"))
        except Exception as exc:
            results.append((name, url, f"ÉCHEC — {type(exc).__name__}: {exc}"))
    return results
