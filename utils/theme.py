"""Thème graphique commun à tous les embeds du bot.

Toute la charte (couleurs, pied de page, séparateurs) est centralisée ici :
modifier ce fichier restyle l'ensemble du bot.
"""

from __future__ import annotations

import discord

# Palette « Arbitration » : or Vitus sur fond sombre.
GOLD = 0xE3B341      # couleur principale (Arbitration, builds)
BLUE = 0x5E9BD6      # informations neutres (analyse standard, help)
GREEN = 0x46A758     # confirmations / maps
RED = 0xE5484D       # erreurs

FOOTER_TEXT = "ArbyFhaps • Arbitration Warframe"
SEPARATOR = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"


def make_embed(
    title: str,
    description: str | None = None,
    *,
    color: int = GOLD,
    footer_extra: str | None = None,
) -> discord.Embed:
    """Embed standard du bot : couleur du thème + pied de page signé."""
    embed = discord.Embed(title=title, description=description, color=color)
    footer = FOOTER_TEXT if not footer_extra else f"{FOOTER_TEXT} — {footer_extra}"
    embed.set_footer(text=footer)
    return embed


def error_embed(message: str) -> discord.Embed:
    return make_embed("❌ Oups", message, color=RED)
