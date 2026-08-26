"""Planning des arbitrations, répliqué depuis browse.wf/arbys.

Le site calcule tout côté client à partir de quatre fichiers publics ; le bot
consomme les mêmes :
 - https://browse.wf/arbys.txt : planning complet, une ligne « epoch,SolNodeXXX »
   par heure (source déterministe pré-générée)
 - ExportRegions.json : méta de chaque nœud (mode MT_*, faction FC_*, clés de nom)
 - dict.<langue>.json : traduction des clés de nom (fr/es/it, sinon en)
 - supplemental-data/arbyTiers.js : notes officielles S→F par nœud (défaut F)

La note affichée suit la priorité : override serveur (/tier-set) > note
officielle browse.wf > repli par mode de mission.
"""

from __future__ import annotations

import bisect
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

BASE = "https://browse.wf"
ARBYS_TXT_URL = f"{BASE}/arbys.txt"
REGIONS_URL = f"{BASE}/warframe-public-export-plus/ExportRegions.json"
TIERS_URL = f"{BASE}/supplemental-data/arbyTiers.js"

# Langues pour lesquelles Warframe fournit une traduction officielle ; les autres
# (no, sv, fi, vi) reçoivent l'anglais, la langue de jeu de ces joueurs
_GAME_LOCALES = {"fr", "es", "it"}


def _dict_url(lang: str) -> str:
    code = lang if lang in _GAME_LOCALES else "en"
    return f"{BASE}/warframe-public-export-plus/dict.{code}.json"

DIAGNOSTIC_URLS = [
    ("planning (arbys.txt)", ARBYS_TXT_URL),
    ("nœuds (ExportRegions)", REGIONS_URL),
    ("traductions FR", f"{BASE}/warframe-public-export-plus/dict.fr.json"),
    ("notes (arbyTiers.js)", TIERS_URL),
]

TIMEOUT = aiohttp.ClientTimeout(total=15)
BIG_TIMEOUT = aiohttp.ClientTimeout(total=90)  # dict/planning : fichiers volumineux

log = logging.getLogger(__name__)

TIER_ORDER = ["S", "A", "B", "C", "D", "F"]
TIER_EMOJI = {"S": "🟡", "A": "🟢", "B": "🔵", "C": "⚪", "D": "🟠", "F": "🔴"}

# Modes de mission (clés MT_* d'ExportRegions) → nom par langue ; les langues
# sans version officielle du jeu retombent sur l'anglais via _named()
TYPE_NAMES = {
    "MT_SURVIVAL": {"fr": "Survie", "en": "Survival", "es": "Supervivencia", "it": "Sopravvivenza"},
    "MT_DEFENSE": {"fr": "Défense", "en": "Defense", "es": "Defensa", "it": "Difesa"},
    "MT_TERRITORY": {"fr": "Interception", "en": "Interception", "es": "Intercepción", "it": "Intercettazione"},
    "MT_EXCAVATE": {"fr": "Excavation", "en": "Excavation", "es": "Excavación", "it": "Scavo"},
    "MT_PURIFY": {"fr": "Sauvetage Infesté", "en": "Infested Salvage",
                  "es": "Salvamento Infestado", "it": "Recupero Infestato"},
    "MT_EVACUATION": {"fr": "Défection", "en": "Defection", "es": "Deserción", "it": "Defezione"},
    "MT_ARTIFACT": {"fr": "Perturbation", "en": "Disruption", "es": "Disrupción", "it": "Disgregazione"},
    "MT_CORRUPTION": {"fr": "Déluge du Vide", "en": "Void Flood",
                      "es": "Inundación del Vacío", "it": "Inondazione del Vuoto"},
    "MT_VOID_CASCADE": {"fr": "Cascade du Vide", "en": "Void Cascade",
                        "es": "Cascada del Vacío", "it": "Cascata del Vuoto"},
    "MT_ARMAGEDDON": {"fr": "Armageddon du Vide", "en": "Void Armageddon",
                      "es": "Armagedón del Vacío", "it": "Armageddon del Vuoto"},
    "MT_ALCHEMY": {"fr": "Alchimie", "en": "Alchemy", "es": "Alquimia", "it": "Alchimia"},
}

FACTION_NAMES = {
    "FC_GRINEER": {"fr": "Grineer", "en": "Grineer", "es": "Grineer", "it": "Grineer"},
    "FC_CORPUS": {"fr": "Corpus", "en": "Corpus", "es": "Corpus", "it": "Corpus"},
    "FC_INFESTATION": {"fr": "Infestés", "en": "Infested", "es": "Infestados", "it": "Infestati"},
    "FC_OROKIN": {"fr": "Corrompus", "en": "Corrupted", "es": "Corruptos", "it": "Corrotti"},
    "FC_MITW": {"fr": "Le Murmure", "en": "The Murmur", "es": "El Murmullo", "it": "Il Mormorio"},
}


def _named(table: dict, key: str, lang: str) -> str | None:
    entry = table.get(key)
    if not entry:
        return None
    return entry.get(lang) or entry["en"]

# Repli si arbyTiers.js est indisponible (sinon la note officielle prime)
TYPE_TIER = {
    "MT_SURVIVAL": "A",
    "MT_DEFENSE": "A",
    "MT_ARTIFACT": "A",
    "MT_EXCAVATE": "B",
    "MT_TERRITORY": "B",
    "MT_VOID_CASCADE": "B",
    "MT_ALCHEMY": "C",
    "MT_CORRUPTION": "C",
    "MT_ARMAGEDDON": "C",
    "MT_PURIFY": "D",
    "MT_EVACUATION": "F",
}

_TIER_PAIR_RE = re.compile(r"[\"']?((?:Sol|Clan)Node\d+)[\"']?\s*:\s*[\"']([SABCDF])[\"']")


@dataclass
class Arbitration:
    solnode: str             # ex : SolNode211
    node: str                # nom affichable, ex : Casta (Cérès)
    mission_type: str        # nom affichable, localisé
    type_key: str            # clé MT_* (pour le repli de notation)
    enemy: str
    activation: datetime | None = None
    expiry: datetime | None = None
    source_tier: str | None = None  # note officielle browse.wf


def rate(arby: Arbitration, guild_overrides: dict[str, str] | None = None) -> str:
    """Note F → S : override serveur > note browse.wf > repli par mode."""
    if guild_overrides:
        for key in (arby.node.lower(), arby.solnode.lower()):
            tier = guild_overrides.get(key)
            if tier in TIER_ORDER:
                return tier
    if arby.source_tier in TIER_ORDER:
        return arby.source_tier
    return TYPE_TIER.get(arby.type_key, "C")


# ---------------------------------------------------------------------------
# Téléchargement + caches
# ---------------------------------------------------------------------------

_TTL_SCHEDULE = 6 * 3600
_TTL_STATIC = 24 * 3600
_TTL_FAIL = 600

_schedule_cache: dict = {"fetched_at": None, "entries": None}
_static_cache: dict = {"fetched_at": None, "regions": None, "dicts": {}, "tiers": None}


def _bundled_tiers() -> dict | None:
    """Copie locale de data/arby_tiers.json (secours si le site est injoignable)."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "data" / "arby_tiers.json"
    try:
        with path.open(encoding="utf-8") as f:
            tiers = json.load(f).get("tiers")
        return tiers if isinstance(tiers, dict) else None
    except Exception:
        return None


def _expired(fetched_at: datetime | None, ok: bool, ttl_ok: int) -> bool:
    if fetched_at is None:
        return True
    ttl = ttl_ok if ok else _TTL_FAIL
    return (datetime.now(timezone.utc) - fetched_at).total_seconds() >= ttl


async def _get_text(session: aiohttp.ClientSession, url: str,
                    timeout: aiohttp.ClientTimeout = TIMEOUT) -> str:
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.text()


async def _get_json(session: aiohttp.ClientSession, url: str,
                    timeout: aiohttp.ClientTimeout = TIMEOUT):
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.json(content_type=None)


async def _load_schedule(session: aiohttp.ClientSession) -> list[tuple[int, str]] | None:
    """arbys.txt → [(epoch, SolNodeXXX), …] trié. None si indisponible."""
    if not _expired(_schedule_cache["fetched_at"], _schedule_cache["entries"] is not None, _TTL_SCHEDULE):
        return _schedule_cache["entries"]
    entries = None
    try:
        text = await _get_text(session, ARBYS_TXT_URL, timeout=BIG_TIMEOUT)
        entries = []
        for line in text.splitlines():
            parts = line.strip().split(",")
            if len(parts) == 2 and parts[0].isdigit():
                entries.append((int(parts[0]), parts[1].strip()))
        entries.sort(key=lambda e: e[0])
        log.info("Planning browse.wf récupéré (%d heures)", len(entries))
    except Exception as exc:
        log.warning("Planning arbys.txt indisponible : %s", exc)
    _schedule_cache["entries"] = entries
    _schedule_cache["fetched_at"] = datetime.now(timezone.utc)
    return entries


async def _load_static(session: aiohttp.ClientSession, lang: str = "fr") -> dict:
    """Charge ExportRegions, arbyTiers et le dictionnaire de la langue demandée."""
    dict_url = _dict_url(lang)
    ok = _static_cache["regions"] is not None
    if not _expired(_static_cache["fetched_at"], ok, _TTL_STATIC):
        if dict_url not in _static_cache["dicts"]:
            await _load_dict(session, dict_url)
        return _static_cache

    regions = None
    try:
        regions = await _get_json(session, REGIONS_URL, timeout=BIG_TIMEOUT)
        if not isinstance(regions, dict):
            regions = None
    except Exception as exc:
        log.warning("ExportRegions indisponible : %s", exc)

    _static_cache["dicts"] = {}
    await _load_dict(session, dict_url)

    tiers = None
    try:
        js = await _get_text(session, TIERS_URL)
        tiers = dict(_TIER_PAIR_RE.findall(js)) or None
        if tiers:
            log.info("Notes officielles chargées (%d nœuds)", len(tiers))
    except Exception as exc:
        log.warning("arbyTiers.js indisponible : %s", exc)
    if tiers is None:
        tiers = _bundled_tiers()
        if tiers:
            log.info("Notes officielles : copie locale de secours (%d nœuds)", len(tiers))

    _static_cache.update(
        regions=regions, tiers=tiers,
        fetched_at=datetime.now(timezone.utc),
    )
    return _static_cache


async def _load_dict(session: aiohttp.ClientSession, url: str) -> None:
    try:
        loc_dict = await _get_json(session, url, timeout=BIG_TIMEOUT)
        if isinstance(loc_dict, dict):
            log.info("Dictionnaire chargé : %s (%d clés)", url, len(loc_dict))
            _static_cache["dicts"][url] = loc_dict
            return
    except Exception as exc:
        log.warning("Dictionnaire %s indisponible : %s", url, exc)
    _static_cache["dicts"][url] = None


# ---------------------------------------------------------------------------
# Construction des arbitrations
# ---------------------------------------------------------------------------

def _loc(loc_dict: dict | None, key: str | None) -> str | None:
    if not key:
        return None
    if loc_dict and key in loc_dict:
        return str(loc_dict[key])
    return None


def _make_arbitration(ts: int, solnode: str, static: dict, lang: str = "fr") -> Arbitration:
    regions = static.get("regions") or {}
    loc_dict = static.get("dicts", {}).get(_dict_url(lang))
    tiers = static.get("tiers")

    meta = regions.get(solnode, {}) if isinstance(regions, dict) else {}
    name = _loc(loc_dict, meta.get("name")) or solnode
    system = _loc(loc_dict, meta.get("systemName"))
    node = f"{name} ({system})" if system else name

    type_key = str(meta.get("missionType") or "?")
    mission_type = (_named(TYPE_NAMES, type_key, lang)
                    or _loc(loc_dict, meta.get("missionName")) or "Arbitration")
    faction_key = str(meta.get("faction") or "")
    enemy = _named(FACTION_NAMES, faction_key, lang) or faction_key

    # Même règle que le site : nœud absent d'arbyTiers → F ; fichier absent → repli
    source_tier = (tiers.get(solnode, "F") if tiers else None)

    start = datetime.fromtimestamp(ts, tz=timezone.utc)
    return Arbitration(
        solnode=solnode,
        node=node,
        mission_type=mission_type,
        type_key=type_key,
        enemy=enemy,
        activation=start,
        expiry=datetime.fromtimestamp(ts + 3600, tz=timezone.utc),
        source_tier=source_tier,
    )


async def get_current_and_upcoming(
    session: aiohttp.ClientSession, limit: int = 6, lang: str = "fr"
) -> tuple[Arbitration | None, list[Arbitration]]:
    """(arbitration en cours, prochaines) d'après le planning browse.wf."""
    entries = await _load_schedule(session)
    if not entries:
        return None, []
    static = await _load_static(session, lang)

    now = int(datetime.now(timezone.utc).timestamp())
    # Le planning couvre plusieurs années : on saute directement à l'heure
    # courante au lieu de le parcourir en entier à chaque actualisation
    times = [ts for ts, _ in entries]
    idx = bisect.bisect_right(times, now) - 1

    current: Arbitration | None = None
    if idx >= 0:
        ts, solnode = entries[idx]
        if ts <= now < ts + 3600:
            current = _make_arbitration(ts, solnode, static, lang)

    upcoming = [
        _make_arbitration(ts, solnode, static, lang)
        for ts, solnode in entries[idx + 1: idx + 1 + limit]
        if ts > now
    ]
    return current, upcoming


async def known_nodes(session: aiohttp.ClientSession) -> list[tuple[str, str]]:
    """Nœuds uniques du planning [(solnode, nom affiché FR)], pour l'autocomplétion."""
    entries = await _load_schedule(session)
    if not entries:
        return []
    static = await _load_static(session, "fr")
    seen: dict[str, str] = {}
    for _, solnode in entries:
        if solnode not in seen:
            seen[solnode] = _make_arbitration(0, solnode, static, "fr").node
    return sorted(seen.items(), key=lambda kv: kv[1])


# ---------------------------------------------------------------------------
# Diagnostics (/sources)
# ---------------------------------------------------------------------------

async def probe_sources(session: aiohttp.ClientSession) -> list[tuple[str, str, str]]:
    """(nom, url, résultat court) pour chaque source de données."""
    results = []
    for name, url in DIAGNOSTIC_URLS:
        try:
            # BIG_TIMEOUT : plusieurs de ces fichiers pèsent des Mo — un probe qui
            # expirerait à 15 s ferait croire à une panne alors que le vrai
            # pipeline (lui aussi en BIG_TIMEOUT) fonctionne
            async with session.get(url, timeout=BIG_TIMEOUT) as resp:
                body = (await resp.text())[:180].replace("\n", " ")
                results.append((name, url, f"HTTP {resp.status} — {body}"))
        except Exception as exc:
            results.append((name, url, f"ÉCHEC — {type(exc).__name__}: {exc}"))
    return results


async def inspect_schedule(session: aiohttp.ClientSession) -> str:
    """Résumé lisible de ce que le bot comprend du planning (pour /sources)."""
    entries = await _load_schedule(session)
    if not entries:
        return "Planning arbys.txt inaccessible ou vide."
    static = await _load_static(session)

    now = datetime.now(timezone.utc)
    first = datetime.fromtimestamp(entries[0][0], tz=timezone.utc)
    last = datetime.fromtimestamp(entries[-1][0] + 3600, tz=timezone.utc)
    current, upcoming = await get_current_and_upcoming(session)

    lines = [
        f"{len(entries)} heures de planning",
        f"Couverture : {first:%Y-%m-%d %H:%M} → {last:%Y-%m-%d %H:%M} UTC",
        f"Nœuds connus : {len(static.get('regions') or {})} | Traductions : "
        f"{'oui' if static.get('dicts', {}).get(_dict_url('fr')) else 'NON'} | Notes officielles : "
        f"{len(static.get('tiers') or {}) or 'NON'}",
        f"En cours : {current.node + ' · ' + current.mission_type if current else 'NON TROUVÉE'}",
        f"Prochaines trouvées : {len(upcoming)}",
    ]
    if last < now:
        lines.append("⚠️ PLANNING PÉRIMÉ : la dernière entrée est dans le passé.")
    return "\n".join(lines)
