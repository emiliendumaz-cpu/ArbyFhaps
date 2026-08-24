"""Cog /analyse : analyse anonymisée d'un fichier EE.log uploadé."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import eelog


class Analyse(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="analyse",
        description="Analyse une run à partir de ton fichier EE.log (données sensibles supprimées).",
    )
    @app_commands.describe(fichier="Ton fichier EE.log (dans %LOCALAPPDATA%/Warframe/)")
    async def analyse(self, interaction: discord.Interaction, fichier: discord.Attachment):
        # L'analyse peut prendre quelques secondes sur un gros log.
        await interaction.response.defer(ephemeral=False)

        if fichier.size > eelog.MAX_LOG_BYTES:
            await interaction.followup.send(
                f"❌ Fichier trop volumineux ({fichier.size / 1024 / 1024:.1f} Mo, "
                f"max {eelog.MAX_LOG_BYTES // 1024 // 1024} Mo). "
                "Astuce : relance Warframe avant ta run pour repartir d'un log vide."
            )
            return

        filename = (fichier.filename or "").lower()
        if not (filename.endswith(".log") or filename.endswith(".txt")):
            await interaction.followup.send(
                "❌ Merci d'envoyer un fichier `.log` ou `.txt` (normalement `EE.log`)."
            )
            return

        try:
            raw_bytes = await fichier.read()
        except discord.HTTPException:
            await interaction.followup.send("❌ Impossible de télécharger le fichier, réessaie.")
            return

        # Décodage + anonymisation + analyse, tout en mémoire. Le contenu brut
        # est libéré aussitôt : rien n'est conservé ni écrit sur disque.
        text = eelog.decode_log_bytes(raw_bytes)
        del raw_bytes
        report = eelog.parse_log(text)
        del text

        embed = self._build_embed(report, interaction.user)
        await interaction.followup.send(embed=embed)

    def _build_embed(self, report: eelog.RunReport, user: discord.abc.User) -> discord.Embed:
        color = discord.Color.gold() if report.is_arbitration else discord.Color.blurple()
        embed = discord.Embed(
            title="📊 Analyse de run" + (" — Arbitration ✅" if report.is_arbitration else ""),
            color=color,
            description="🔒 Toutes les données sensibles (IP, identifiants, chemins système) "
            "ont été supprimées avant l'analyse. Le fichier n'est pas conservé.",
        )
        embed.set_footer(text=f"Demandé par {user.display_name}")

        embed.add_field(name="Nœud", value=report.mission_node or "Non détecté", inline=True)
        embed.add_field(
            name="Type de mission",
            value=_pretty_mission_type(report.mission_type),
            inline=True,
        )
        embed.add_field(name="Durée", value=report.duration_text, inline=True)

        embed.add_field(
            name="Escouade",
            value="\n".join(f"• {p}" for p in report.players) if report.players else "Non détectée",
            inline=True,
        )
        embed.add_field(
            name="Warframes détectées",
            value=", ".join(report.warframes) if report.warframes else "Non détectées",
            inline=True,
        )
        embed.add_field(
            name="Fin de mission",
            value="✅ Détectée" if report.ended_properly else "❓ Non détectée",
            inline=True,
        )

        if report.notes:
            embed.add_field(name="Remarques", value="\n".join(f"– {n}" for n in report.notes), inline=False)

        return embed


_MISSION_TYPE_FR = {
    "MT_SURVIVAL": "Survie",
    "MT_DEFENSE": "Défense",
    "MT_INTERCEPTION": "Interception",
    "MT_EXCAVATE": "Excavation",
    "MT_ARTIFACT": "Défense mobile",
    "MT_TERRITORY": "Interception",
    "MT_DISRUPTION": "Disruption",
    "MT_ENDLESS_EXTERMINATION": "Extermination sans fin",
}


def _pretty_mission_type(mtype: str | None) -> str:
    if not mtype:
        return "Non détecté"
    return _MISSION_TYPE_FR.get(mtype, mtype)


async def setup(bot: commands.Bot):
    await bot.add_cog(Analyse(bot))
