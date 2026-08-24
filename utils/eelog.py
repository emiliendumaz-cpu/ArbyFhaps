"""Parsing et anonymisation du fichier EE.log de Warframe.

Principe de confidentialité : le fichier est ANONYMISÉ AVANT toute analyse.
Les IPs (v4/v6), ports, GUID/IDs de compte, adresses MAC et chemins système
sont supprimés du texte dès la lecture ; le parseur ne travaille que sur la
version nettoyée et le bot ne stocke jamais le fichier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_LOG_BYTES = 30 * 1024 * 1024  # 30 Mo, largement au-dessus d'un EE.log normal

# ---------------------------------------------------------------------------
# Anonymisation
# ---------------------------------------------------------------------------

_SANITIZE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # IPv4 avec port éventuel (ex: 192.168.1.10:4950)
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d{1,5})?\b"), "[ip-supprimée]"),
    # IPv6 (forme complète ou abrégée, au moins deux ':')
    (re.compile(r"\b(?:[0-9A-Fa-f]{1,4}:){2,7}[0-9A-Fa-f]{0,4}\b"), "[ip-supprimée]"),
    # Adresses MAC
    (re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "[mac-supprimée]"),
    # GUID / IDs de compte (hex de 16 caractères ou plus)
    (re.compile(r"\b[0-9a-fA-F]{16,}\b"), "[id-supprimé]"),
    # Chemins Windows contenant le nom d'utilisateur système
    (re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+", re.IGNORECASE), r"C:\\Users\\[utilisateur]"),
    # Login du compte (ligne "Logged in <pseudo> (id)")
    (re.compile(r"(Logged in )\S+", re.IGNORECASE), r"\1[compte]"),
]


def sanitize(text: str) -> str:
    """Supprime toute donnée sensible (IP, port, ID, MAC, chemins, login)."""
    for pattern, repl in _SANITIZE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

@dataclass
class RunReport:
    mission: str | None = None
    duration_s: float | None = None
    players: list[str] = field(default_factory=list)
    host_migrations: int = 0
    joins: int = 0
    leaves: int = 0
    is_arbitration: bool = False
    warnings: int = 0
    errors: int = 0
    lines: int = 0

    @property
    def duration_text(self) -> str:
        if self.duration_s is None:
            return "inconnue"
        total = int(self.duration_s)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m:02d}min {s:02d}s" if h else f"{m}min {s:02d}s"


_TIMESTAMP_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s+\w+\s+\[(\w+)\]")
_MISSION_RES = [
    re.compile(r"Host loading\s+(?:level\s+)?[\"']?([^\"'\r\n]+?)[\"']?\s*$", re.IGNORECASE),
    re.compile(r"MissionName:\s*(.+?)\s*$", re.IGNORECASE),
    re.compile(r"Mission name:\s*(.+?)\s*$", re.IGNORECASE),
]
_ARBITRATION_RE = re.compile(r"arbitration|elitealertmission", re.IGNORECASE)
_HOST_MIGRATION_RE = re.compile(r"host migration", re.IGNORECASE)
_JOIN_RE = re.compile(r"^(?:Script \[Info\]:\s*)?.*?(\S+)\s+(?:a rejoint|has joined|joined squad)", re.IGNORECASE)
_LEAVE_RE = re.compile(r"(?:has left|a quitté|left squad)", re.IGNORECASE)
_PLAYER_NAME_RE = re.compile(r"ThemedSquadOverlay\.lua:\s*(\S+?)\s+(?:has joined|joined|a rejoint)", re.IGNORECASE)


def parse(raw_text: str) -> RunReport:
    """Analyse un EE.log déjà lu ; l'anonymisation est appliquée ici même."""
    text = sanitize(raw_text)
    report = RunReport()

    first_ts: float | None = None
    last_ts: float | None = None
    players: list[str] = []

    for line in text.splitlines():
        report.lines += 1

        m = _TIMESTAMP_RE.match(line)
        if m:
            ts = float(m.group(1))
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            level = m.group(2).lower()
            if level == "warning":
                report.warnings += 1
            elif level == "error":
                report.errors += 1

        if report.mission is None:
            for mission_re in _MISSION_RES:
                mm = mission_re.search(line)
                if mm:
                    report.mission = mm.group(1).strip()
                    break

        if _ARBITRATION_RE.search(line):
            report.is_arbitration = True

        if _HOST_MIGRATION_RE.search(line):
            report.host_migrations += 1

        pm = _PLAYER_NAME_RE.search(line)
        if pm:
            name = pm.group(1).strip()
            if name and name not in players and "[" not in name:
                players.append(name)

        if _JOIN_RE.search(line):
            report.joins += 1
        if _LEAVE_RE.search(line):
            report.leaves += 1

    if first_ts is not None and last_ts is not None and last_ts > first_ts:
        report.duration_s = last_ts - first_ts

    report.players = players[:8]
    return report
