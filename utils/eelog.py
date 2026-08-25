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

SATURATION_BUCKETS = ["0-2", "3-5", "6-8", "9-11", "12-14", "15-17", "18-20", "21-23", "24-26", "27+"]
N_INTERVALS = 5


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
    # Statistiques de spawn (présentes si le log contient les événements d'agents)
    total_spawns: int = 0
    drones_spawned: int = 0
    drones_killed: int = 0
    # Comptes bruts : « strict » = drones d'Arbitration identifiés comme tels,
    # « large » = toute entité nommée drone (inclut les drones de tileset Corpus)
    drones_killed_strict: int = 0
    drones_killed_loose: int = 0
    drone_source: str = ""   # "arbitration" | "large" | "saisi"
    vitus_pickups: int = 0
    vitus_source: str = ""   # "log" | "saisi"
    waves: int = 0
    saturation: dict[str, float] = field(default_factory=dict)  # bucket -> % du temps
    interval_drones: list[int] = field(default_factory=list)
    interval_spawns: list[int] = field(default_factory=list)

    @property
    def has_spawn_data(self) -> bool:
        return self.total_spawns > 0

    @property
    def kills_per_drone(self) -> float | None:
        return self.total_spawns / self.drones_killed if self.drones_killed else None

    @property
    def avg_drone_interval_s(self) -> float | None:
        if self.drones_killed and self.duration_s:
            return self.duration_s / self.drones_killed
        return None

    @property
    def vitus_per_minute(self) -> float | None:
        if self.vitus_pickups and self.duration_s:
            return self.vitus_pickups / (self.duration_s / 60)
        return None

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
# Événements d'agents (spawn/mort des ennemis) — plusieurs variantes selon les versions du jeu
_AGENT_CREATED_RE = re.compile(r"(?:OnAgentCreated|AgentCreated|CreateAgent)\s+(/\S+)", re.IGNORECASE)
_AGENT_DESTROYED_RE = re.compile(r"(?:OnAgentDestroyed|AgentDestroyed|DestroyAgent)\s+(/\S+)", re.IGNORECASE)
# Drones d'Arbitration (ceux qui droppent la Vitus) : leur chemin d'agent contient
# « arbitration »/« elitealert ». Les tilesets Corpus ont leurs propres drones qui
# ne droppent rien — d'où un compte strict, et un compte large en repli seulement.
_ARBY_DRONE_RE = re.compile(r"(?=.*drone)(?=.*(?:arbitration|elitealert))", re.IGNORECASE)
_DRONE_RE = re.compile(r"drone", re.IGNORECASE)
_VITUS_RE = re.compile(r"VitusEssence", re.IGNORECASE)
_WAVE_RE = re.compile(r"\bwave\s+(\d+)\b", re.IGNORECASE)


def parse(raw_text: str) -> RunReport:
    """Analyse un EE.log déjà lu ; l'anonymisation est appliquée ici même."""
    text = sanitize(raw_text)
    report = RunReport()

    first_ts: float | None = None
    last_ts: float | None = None
    players: list[str] = []
    # Événements (timestamp, delta_vivants, est_un_drone, est_un_drone_d_arbitration)
    agent_events: list[tuple[float, int, bool, bool]] = []
    current_ts: float | None = None

    for line in text.splitlines():
        report.lines += 1

        m = _TIMESTAMP_RE.match(line)
        if m:
            ts = float(m.group(1))
            if first_ts is None:
                first_ts = ts
            last_ts = ts
            current_ts = ts
            level = m.group(2).lower()
            if level == "warning":
                report.warnings += 1
            elif level == "error":
                report.errors += 1

        cm = _AGENT_CREATED_RE.search(line)
        dm = None if cm else _AGENT_DESTROYED_RE.search(line)
        if cm or dm:
            path = (cm or dm).group(1)
            is_drone = bool(_DRONE_RE.search(path))
            is_arby_drone = is_drone and bool(_ARBY_DRONE_RE.search(path))
            if cm:
                if is_drone:
                    report.drones_spawned += 1
                else:
                    report.total_spawns += 1
            else:
                if is_drone:
                    report.drones_killed_loose += 1
                if is_arby_drone:
                    report.drones_killed_strict += 1
            if current_ts is not None:
                agent_events.append((current_ts, 1 if cm else -1, is_drone, is_arby_drone))

        if _VITUS_RE.search(line):
            report.vitus_pickups += 1

        wm = _WAVE_RE.search(line)
        if wm:
            report.waves = max(report.waves, int(wm.group(1)))

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
    # Les drones d'Arbitration identifiés comme tels priment ; sinon repli sur le
    # compte large, forcément moins sûr (drones de tileset inclus)
    if report.drones_killed_strict:
        report.drones_killed = report.drones_killed_strict
        report.drone_source = "arbitration"
    elif report.drones_killed_loose:
        report.drones_killed = report.drones_killed_loose
        report.drone_source = "large"
    if report.vitus_pickups:
        report.vitus_source = "log"
    _compute_spawn_stats(report, agent_events)
    return report


def apply_overrides(report: RunReport, vitus: int | None = None,
                    drones: int | None = None) -> RunReport:
    """Remplace les valeurs déduites du log par celles saisies par le joueur.

    Le EE.log ne journalise pas les ramassages de façon fiable : une valeur
    saisie fait autorité et rend l'analyse exacte.
    """
    if vitus is not None:
        report.vitus_pickups = vitus
        report.vitus_source = "saisi"
    if drones is not None:
        report.drones_killed = drones
        report.drone_source = "saisi"
    return report


def _bucket_index(alive: int) -> int:
    return min(alive // 3, len(SATURATION_BUCKETS) - 1)


def _compute_spawn_stats(report: RunReport, events: list[tuple[float, int, bool, bool]]) -> None:
    """Saturation ennemis (% du temps par nombre d'ennemis vivants) et stats par intervalle."""
    if not events:
        return

    t0, t1 = events[0][0], events[-1][0]
    span = t1 - t0
    if span <= 0:
        return

    # Saturation : temps passé à chaque palier d'ennemis vivants (drones exclus)
    bucket_time = [0.0] * len(SATURATION_BUCKETS)
    alive = 0
    prev_ts = t0
    for ts, delta, is_drone, _ in events:
        bucket_time[_bucket_index(alive)] += ts - prev_ts
        prev_ts = ts
        if not is_drone:
            alive = max(0, alive + delta)
    report.saturation = {
        label: 100.0 * t / span for label, t in zip(SATURATION_BUCKETS, bucket_time)
    }

    # Découpage de la mission en intervalles égaux : spawns et drones tués par intervalle
    interval_spawns = [0] * N_INTERVALS
    interval_drones = [0] * N_INTERVALS
    strict = report.drone_source == "arbitration"
    for ts, delta, is_drone, is_arby_drone in events:
        idx = min(int((ts - t0) / span * N_INTERVALS), N_INTERVALS - 1)
        # Même population de drones que la tuile « Drones tués », sinon les deux
        # chiffres se contrediraient
        if delta == -1 and (is_arby_drone if strict else is_drone):
            interval_drones[idx] += 1
        elif not is_drone and delta == 1:
            interval_spawns[idx] += 1
    report.interval_spawns = interval_spawns
    report.interval_drones = interval_drones
