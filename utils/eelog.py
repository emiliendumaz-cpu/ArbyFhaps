"""
Analyse du fichier EE.log de Warframe, avec anonymisation stricte.

Principe de confidentialité (non négociable dans ce module) :
  1. Le contenu brut du log est anonymisé AVANT toute analyse.
  2. Aucune donnée sensible (IP, ports, IDs de compte, chemins système,
     identifiants réseau) ne survit à `sanitize()` — l'analyse ne peut donc
     jamais en faire fuiter, même par accident.
  3. Rien n'est écrit sur le disque : tout se passe en mémoire.

Le format d'EE.log n'est pas documenté officiellement par Digital Extremes ;
le parseur est donc « best-effort » : il extrait ce qu'il reconnaît et
signale proprement ce qu'il ne trouve pas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Taille max acceptée pour un log (les EE.log peuvent être très gros).
MAX_LOG_BYTES = 30 * 1024 * 1024  # 30 Mo

# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------

_SANITIZE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # IPv4 (avec port éventuel) : 123.45.67.89:4950
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?\b"), "[IP-SUPPRIMÉE]"),
    # IPv6
    (re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{1,4}\b"), "[IP-SUPPRIMÉE]"),
    # Identifiants de compte / GUID (longues chaînes hexadécimales)
    (re.compile(r"\b[0-9a-fA-F]{16,}\b"), "[ID-SUPPRIMÉ]"),
    # GUID au format 8-4-4-4-12
    (
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
            r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
        "[ID-SUPPRIMÉ]",
    ),
    # Chemins Windows contenant le nom d'utilisateur de la machine
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.IGNORECASE), r"C:\\Users\\[UTILISATEUR]"),
    # Lignes réseau bas niveau (NAT, ping, relais…) : on vide la partie données
    (
        re.compile(r"^(.*\bNet \[Info\]:.*(?:NAT|PUNCH|RELAY|ping|port).*)$", re.IGNORECASE | re.MULTILINE),
        "[LIGNE-RÉSEAU-SUPPRIMÉE]",
    ),
    # Tokens / tickets de session
    (re.compile(r"(ticket|token|nonce|accountId)\s*[=:]\s*\S+", re.IGNORECASE), r"\1=[SUPPRIMÉ]"),
]


def sanitize(raw: str) -> str:
    """Retourne une copie du log expurgée de toute donnée sensible."""
    cleaned = raw
    for pattern, replacement in _SANITIZE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class RunReport:
    """Résumé anonymisé d'une run extraite d'un EE.log."""

    mission_node: str | None = None
    mission_name: str | None = None
    mission_type: str | None = None
    is_arbitration: bool = False
    duration_seconds: float | None = None
    host_migrations: int = 0
    players: list[str] = field(default_factory=list)
    warframes: list[str] = field(default_factory=list)
    ended_properly: bool = False
    # Remarques sous forme de clés de traduction (voir utils/i18n.py) :
    # liste de tuples (clé, paramètres de format).
    notes: list[tuple[str, dict]] = field(default_factory=list)

    @property
    def duration_text(self) -> str | None:
        """Durée formatée (neutre en langue), ou None si inconnue."""
        if self.duration_seconds is None:
            return None
        total = int(self.duration_seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        if h:
            return f"{h}h {m:02d}m {s:02d}s"
        return f"{m}m {s:02d}s"


# Timestamp en début de ligne : "1234.567 Sys [Info]: ..."
_RE_TIMESTAMP = re.compile(r"^(\d+(?:\.\d+)?)\s")

# Nœud de mission ("SolNode123", "SettlementNode20"…)
_RE_NODE = re.compile(r"\b((?:Sol|Settlement|Clan|Crew|Erpo)Node\d+)\b")

# Type de mission interne ("MT_SURVIVAL", "MT_DEFENSE"…)
_RE_MISSION_TYPE = re.compile(r"\b(MT_[A-Z_]+)\b")

# Chargement de mission côté host/client
_RE_LOADING = re.compile(r"(?:Host loading|Client loading|loading level)", re.IGNORECASE)

# Détection arbitration
_RE_ARBITRATION = re.compile(r"arbitration|elitealert", re.IGNORECASE)

# Joueurs rejoignant l'escouade. Les pseudos Warframe sont alphanumériques
# (+ '.' et '-'), éventuellement suffixés par la plateforme.
_RE_PLAYER_JOIN = re.compile(
    r"(?:AddSquadMember|added squad member|(?<!\w)joined squad|has joined)"
    r"[^\w]*[:\s]([A-Za-z0-9_.\-]{2,32})",
    re.IGNORECASE,
)

# Migration d'hôte
_RE_HOST_MIGRATION = re.compile(r"host migration", re.IGNORECASE)

# Fin de mission
_RE_END = re.compile(r"EndOfMatch|EOM\.lua|Mission (?:Succeeded|Complete|Failed)", re.IGNORECASE)

# Warframes détectées (liste non exhaustive, sert au résumé de compo)
_KNOWN_WARFRAMES = [
    "Ash", "Atlas", "Banshee", "Baruuk", "Caliban", "Chroma", "Citrine",
    "Cyte-09", "Dagath", "Dante", "Ember", "Equinox", "Excalibur", "Frost",
    "Gara", "Garuda", "Gauss", "Grendel", "Gyre", "Harrow", "Hildryn",
    "Hydroid", "Inaros", "Ivara", "Jade", "Khora", "Kullervo", "Lavos",
    "Limbo", "Loki", "Mag", "Mesa", "Mirage", "Nekros", "Nezha", "Nidus",
    "Nova", "Nyx", "Oberon", "Octavia", "Oraxia", "Protea", "Qorvex",
    "Revenant", "Rhino", "Saryn", "Sevagoth", "Styanax", "Temple", "Titania",
    "Trinity", "Valkyr", "Vauban", "Volt", "Voruna", "Wisp", "Wukong",
    "Xaku", "Yareli", "Zephyr",
]
_RE_WARFRAME = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _KNOWN_WARFRAMES) + r")(?:Prime)?\b",
    re.IGNORECASE,
)


def parse_log(raw: str) -> RunReport:
    """
    Analyse un EE.log (déjà décodé en texte) et retourne un résumé anonymisé.

    Le texte est anonymisé en interne avant analyse : aucune donnée sensible
    ne peut apparaître dans le rapport.
    """
    text = sanitize(raw)
    report = RunReport()

    first_ts: float | None = None
    mission_start_ts: float | None = None
    last_ts: float | None = None
    players: list[str] = []
    frames: dict[str, None] = {}  # dict ordonné == set ordonné

    for line in text.splitlines():
        ts_match = _RE_TIMESTAMP.match(line)
        ts = float(ts_match.group(1)) if ts_match else None
        if ts is not None:
            if first_ts is None:
                first_ts = ts
            last_ts = ts

        if report.mission_node is None:
            node = _RE_NODE.search(line)
            if node:
                report.mission_node = node.group(1)

        if report.mission_type is None:
            mtype = _RE_MISSION_TYPE.search(line)
            if mtype:
                report.mission_type = mtype.group(1)

        if mission_start_ts is None and ts is not None and _RE_LOADING.search(line):
            mission_start_ts = ts

        if not report.is_arbitration and _RE_ARBITRATION.search(line):
            report.is_arbitration = True

        join = _RE_PLAYER_JOIN.search(line)
        if join:
            name = join.group(1)
            if name not in players and not name.startswith("["):
                players.append(name)

        if _RE_HOST_MIGRATION.search(line):
            report.host_migrations += 1

        if _RE_END.search(line):
            report.ended_properly = True

        frame = _RE_WARFRAME.search(line)
        if frame and ("LoadOut" in line or "Avatar" in line or "Loadout" in line):
            frames.setdefault(frame.group(1).title())

    report.players = players[:4]
    report.warframes = list(frames)[:4]

    start = mission_start_ts if mission_start_ts is not None else first_ts
    if start is not None and last_ts is not None and last_ts > start:
        report.duration_seconds = last_ts - start
        if mission_start_ts is None:
            report.notes.append(("an.note_est_duration", {}))

    if not report.is_arbitration:
        report.notes.append(("an.note_not_arby", {}))
    if report.host_migrations:
        report.notes.append(("an.note_migrations", {"n": report.host_migrations}))
    if not report.ended_properly:
        report.notes.append(("an.note_no_end", {}))

    return report


def decode_log_bytes(data: bytes) -> str:
    """Décode le fichier log en texte, avec tolérance aux octets invalides."""
    return data.decode("utf-8", errors="replace")
