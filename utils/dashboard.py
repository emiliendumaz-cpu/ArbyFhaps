"""Rendu du dashboard /analyse en image PNG (style sombre / or Vitus).

Reproduit la mise en page façon « arbi analyzer » : tuiles de stats, table de
probabilité Vitus, saturation des ennemis et graphiques par intervalle.
"""

from __future__ import annotations

import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from utils.eelog import RunReport, SATURATION_BUCKETS

# Charte sombre (voir utils/theme.py pour la version embed)
PAGE = "#0d0d0d"
TILE = "#1a1a19"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
TRACK = "#2c2c2a"
GOLD = "#e3b341"
GOLD_BAR = "#d9a63a"
RED = "#e5484d"

# Chance de drop de Vitus par drone : 6 % de base × boosters/Récupérateur
# (mêmes hypothèses que l'outil « arbi » de svesk : 100 % de ramassage, tous les buffs)
VITUS_DROP_CHANCE = 0.36

_LUCK_LEVELS = [
    (99, "Pire cas"),
    (90, "Malchanceux"),
    (75, "Sous la moyenne"),
    (50, "Moyenne"),
    (25, "Au-dessus de la moyenne"),
    (10, "Chanceux"),
    (1, "Roll divin"),
]
_Z = {99: -2.326, 90: -1.282, 75: -0.674, 50: 0.0, 25: 0.674, 10: 1.282, 1: 2.326}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return "—"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def _tile(ax, label: str, value: str, caption: str = ""):
    ax.set_facecolor(TILE)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    # Barre d'accent dorée à gauche, signature du thème
    ax.add_patch(Rectangle((0, 0), 0.012, 1, transform=ax.transAxes, color=GOLD, zorder=3))
    ax.text(0.5, 0.80, label.upper(), transform=ax.transAxes, ha="center", va="center",
            color=INK_2, fontsize=10.5, fontweight="bold")
    ax.text(0.5, 0.45, value, transform=ax.transAxes, ha="center", va="center",
            color=INK, fontsize=25, fontweight="bold")
    if caption:
        ax.text(0.5, 0.13, caption, transform=ax.transAxes, ha="center", va="center",
                color=MUTED, fontsize=9.5)


def _style_axes(ax):
    ax.set_facecolor(TILE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=1)
    ax.set_axisbelow(True)


def _line_chart(ax, title: str, subtitle: str, values: list[int]):
    _style_axes(ax)
    ax.set_title(title, color=INK, fontsize=13, fontweight="bold", loc="left", pad=18)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9)
    if not values or not any(values):
        ax.grid(False)
        ax.text(0.5, 0.5, "Données indisponibles", transform=ax.transAxes,
                ha="center", va="center", color=MUTED, fontsize=11)
        ax.set_xticks([])
        return
    x = list(range(1, len(values) + 1))
    avg = sum(values) / len(values)
    ax.axhline(avg, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.plot(x, values, color=GOLD, linewidth=2, solid_joinstyle="round", zorder=3)
    # Marqueurs avec anneau couleur surface pour rester lisibles sur la ligne
    ax.scatter(x, values, s=64, color=GOLD, edgecolors=TILE, linewidths=2, zorder=4)
    # Étiquettes sélectives : min, max et ligne de moyenne
    vmax, vmin = max(values), min(values)
    span = (vmax - vmin) or 1
    for xi, v in zip(x, values):
        if v in (vmax, vmin):
            offset = 0.09 * span if v == vmax else -0.14 * span
            ax.text(xi, v + offset, f"{v:,}".replace(",", " "), ha="center",
                    color=INK, fontsize=9.5, fontweight="bold")
    ax.text(x[-1] + 0.08, avg, f"moy {avg:,.1f}".replace(",", " "), color=INK_2,
            fontsize=9, va="bottom", ha="right")
    ax.set_xticks(x)
    ax.set_xlabel("Intervalle", color=MUTED, fontsize=9)
    ax.margins(y=0.22)


def _luck_table(ax, report: RunReport):
    ax.set_facecolor(TILE)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("Probabilité de Vitus attendue", color=INK, fontsize=13,
                 fontweight="bold", loc="left", pad=18)
    ax.text(0, 1.02, "Hypothèses : 100 % de ramassage, buffs et mod Récupérateur actifs.",
            transform=ax.transAxes, color=MUTED, fontsize=9)

    n = report.drones_killed
    if not n:
        ax.text(0.5, 0.5, "Aucun drone détecté dans le log", transform=ax.transAxes,
                ha="center", va="center", color=MUTED, fontsize=11)
        return

    mean = n * VITUS_DROP_CHANCE
    sd = math.sqrt(n * VITUS_DROP_CHANCE * (1 - VITUS_DROP_CHANCE))

    actual = report.vitus_pickups
    header_y = 0.86
    if actual:
        pct = _norm_cdf((actual - mean) / sd) * 100
        verdict = f"Percentile : {pct:.1f} %"
        ax.text(0.02, 0.93, f"Vitus réels :  {actual}", transform=ax.transAxes,
                color=INK, fontsize=12, fontweight="bold")
        ax.text(0.98, 0.93, verdict, transform=ax.transAxes, ha="right",
                color=RED if pct < 25 else INK_2, fontsize=11, fontweight="bold")

    cols = (0.04, 0.38, 0.66)
    ax.text(cols[0], header_y, "Chance", transform=ax.transAxes, color=INK_2, fontsize=10, fontweight="bold")
    ax.text(cols[1], header_y, "Vitus total", transform=ax.transAxes, color=INK_2, fontsize=10, fontweight="bold")
    ax.text(cols[2], header_y, "Niveau de chance", transform=ax.transAxes, color=INK_2, fontsize=10, fontweight="bold")
    ax.plot([0.02, 0.98], [header_y - 0.035] * 2, transform=ax.transAxes, color=GRID, linewidth=1)

    row_h = 0.105
    y = header_y - 0.09
    prev_vitus = -math.inf
    for chance, label in _LUCK_LEVELS:
        vitus = int(round(mean + _Z[chance] * sd))
        highlight = bool(actual) and prev_vitus < actual <= vitus
        if highlight:
            ax.add_patch(Rectangle((0.02, y - 0.03), 0.96, row_h - 0.02,
                                   transform=ax.transAxes, color=GOLD, alpha=0.14, zorder=1))
        weight = "bold" if highlight else "normal"
        ax.text(cols[0], y, f"{chance} %", transform=ax.transAxes, color=INK_2, fontsize=10.5, fontweight=weight)
        ax.text(cols[1], y, str(vitus), transform=ax.transAxes, color=INK, fontsize=10.5, fontweight="bold")
        ax.text(cols[2], y, label, transform=ax.transAxes, color=INK_2, fontsize=10.5, fontweight=weight)
        prev_vitus = vitus
        y -= row_h


def _saturation_chart(ax, report: RunReport):
    _style_axes(ax)
    ax.grid(False)
    ax.set_title("Saturation ennemis", color=INK, fontsize=13, fontweight="bold",
                 loc="left", pad=18)
    ax.text(0, 1.02, "% du temps par nombre d'ennemis vivants.",
            transform=ax.transAxes, color=MUTED, fontsize=9)

    if not report.saturation:
        ax.text(0.5, 0.5, "Données indisponibles", transform=ax.transAxes,
                ha="center", va="center", color=MUTED, fontsize=11)
        ax.set_xticks([])
        return

    labels = SATURATION_BUCKETS
    values = [report.saturation.get(b, 0.0) for b in labels]
    ypos = list(range(len(labels)))[::-1]
    vmax = max(values) or 1.0

    for y, v in zip(ypos, values):
        ax.barh(y, vmax * 1.08, height=0.55, color=TRACK, zorder=2)
        if v > 0:
            ax.barh(y, v, height=0.55, color=GOLD_BAR, zorder=3)
        ax.text(vmax * 1.12, y, f"{v:.1f} %", va="center", color=INK,
                fontsize=10, fontweight="bold")

    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, color=INK_2, fontsize=10)
    ax.set_xticks([])
    ax.set_xlim(0, vmax * 1.30)

    # Résumé placé sous les barres, à l'intérieur du panneau (pas de collision dessous)
    heavy = sum(v for b, v in report.saturation.items()
                if b in ("15-17", "18-20", "21-23", "24-26", "27+"))
    ax.set_ylim(-1.9, len(labels) - 0.4)
    ax.text(0, -1.35, f"Temps avec ≥ 15 ennemis :  {heavy:.1f} %",
            color=INK, fontsize=11, fontweight="bold")


def render(report: RunReport) -> bytes:
    """Construit le dashboard PNG et retourne ses octets."""
    fig = plt.figure(figsize=(12.8, 14.2), dpi=110)
    fig.patch.set_facecolor(PAGE)

    gs = fig.add_gridspec(
        6, 3,
        height_ratios=[0.55, 0.95, 0.95, 3.4, 2.6, 0.25],
        hspace=0.42, wspace=0.14,
        left=0.045, right=0.955, top=0.965, bottom=0.035,
    )

    # --- En-tête : pastille dorée + nom de mission
    ax_head = fig.add_subplot(gs[0, :])
    ax_head.axis("off")
    ax_head.text(0.5, 0.78, "ANALYSE ARBITRATION" if report.is_arbitration else "ANALYSE DE MISSION",
                 ha="center", va="center", fontsize=13, fontweight="bold", color="#111111",
                 bbox=dict(boxstyle="round,pad=0.55", facecolor=GOLD, edgecolor="none"))
    ax_head.text(0.5, 0.12, (report.mission or "Mission inconnue").upper(),
                 ha="center", va="center", fontsize=15, fontweight="bold", color=INK)

    # --- Tuiles de stats
    kpd = report.kills_per_drone
    interval = report.avg_drone_interval_s
    vpm = report.vitus_per_minute
    tiles = [
        ("Ennemis apparus", f"{report.total_spawns:,}".replace(",", " ") if report.total_spawns else "—",
         "Drones exclus"),
        ("Kills par drone", f"{kpd:.2f}" if kpd else "—", "Ennemis apparus par drone"),
        ("Intervalle drone moyen", f"{interval:.2f}s" if interval else "—",
         "Temps moyen entre deux drones"),
        ("Drones tués", f"{report.drones_killed:,}".replace(",", " ") if report.drones_killed else "—",
         f"{report.drones_spawned} apparus" if report.drones_spawned else ""),
        ("Vitus par minute", f"{vpm:.2f}/m" if vpm else "—",
         f"{report.vitus_pickups} Vitus au total" if report.vitus_pickups else "Aucun ramassage détecté"),
        ("Durée totale", _fmt_duration(report.duration_s),
         f"{report.waves} vagues" if report.waves else ""),
    ]
    for i, (label, value, caption) in enumerate(tiles):
        ax = fig.add_subplot(gs[1 + i // 3, i % 3])
        _tile(ax, label, value, caption)

    # --- Table de chance Vitus + saturation
    _luck_table(fig.add_subplot(gs[3, 0:2]), report)
    _saturation_chart(fig.add_subplot(gs[3, 2]), report)

    # --- Graphiques par intervalle
    _line_chart(fig.add_subplot(gs[4, 0:2]), "Drones par intervalle",
                "Drones tués sur 5 intervalles égaux, avec la moyenne.", report.interval_drones)
    _line_chart(fig.add_subplot(gs[4, 2]), "Spawns par intervalle",
                "Ennemis apparus sur 5 intervalles égaux.", report.interval_spawns)

    # --- Pied de page
    ax_foot = fig.add_subplot(gs[5, :])
    ax_foot.axis("off")
    ax_foot.text(0.5, 0.5, "ArbyFhaps  •  Arbitration Warframe  •  log anonymisé, rien n'est stocké",
                 ha="center", va="center", color=MUTED, fontsize=9.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=PAGE)
    plt.close(fig)
    return buf.getvalue()
