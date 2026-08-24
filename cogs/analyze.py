"""Commande /analyse : analyse d'un EE.log uploadé, avec anonymisation."""

from __future__ import annotations

import asyncio
import io

import discord
from discord import app_commands
from discord.ext import commands

from utils import dashboard, eelog, theme


class AnalyzeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="analyse",
        description="Analyse un fichier EE.log de Warframe (IPs et données perso supprimées automatiquement).",
    )
    @app_commands.describe(fichier="Votre fichier EE.log (Windows : %LOCALAPPDATA%\\Warframe\\EE.log)")
    async def analyse(self, interaction: discord.Interaction, fichier: discord.Attachment):
        if fichier.size > eelog.MAX_LOG_BYTES:
            await interaction.response.send_message(
                embed=theme.error_embed("Fichier trop volumineux (max 30 Mo)."), ephemeral=True
            )
            return

        name_lower = fichier.filename.lower()
        if not (name_lower.endswith(".log") or name_lower.endswith(".txt")):
            await interaction.response.send_message(
                embed=theme.error_embed(
                    "Merci d'envoyer un fichier `.log` ou `.txt` (le fichier EE.log de Warframe)."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = (await fichier.read()).decode("utf-8", errors="replace")
        report = eelog.parse(raw)
        del raw  # le contenu brut n'est jamais conservé

        # Log riche (événements de spawn présents) → dashboard image façon « arbi analyzer »
        if report.has_spawn_data:
            png = await asyncio.to_thread(dashboard.render, report)
            file = discord.File(io.BytesIO(png), filename="analyse-arbitration.png")
            embed = theme.make_embed(
                "📊 Analyse du run",
                "🔒 *Fichier anonymisé avant analyse : IPs, ports, IDs de compte et "
                "chemins système supprimés. Rien n'est stocké.*",
                color=theme.GOLD if report.is_arbitration else theme.BLUE,
                footer_extra=f"{report.lines} lignes analysées",
            )
            if report.players:
                embed.add_field(
                    name="👥 Joueurs (pseudos en jeu)",
                    value=" • ".join(f"`{p}`" for p in report.players),
                    inline=False,
                )
            embed.set_image(url="attachment://analyse-arbitration.png")
            await interaction.followup.send(embed=embed, file=file)
            return

        is_arby = report.is_arbitration
        embed = theme.make_embed(
            "📊 Analyse du run",
            f"{'⚖️ **Arbitration détectée**' if is_arby else '🎮 Mission standard'}\n{theme.SEPARATOR}",
            color=theme.GOLD if is_arby else theme.BLUE,
            footer_extra=f"{report.lines} lignes analysées",
        )
        embed.add_field(name="🗺️ Mission", value=report.mission or "*Non détectée*", inline=True)
        embed.add_field(name="⏱️ Durée de session", value=report.duration_text, inline=True)
        embed.add_field(name="🔄 Migrations d'hôte", value=str(report.host_migrations), inline=True)

        if report.players:
            embed.add_field(
                name="👥 Joueurs détectés (pseudos en jeu)",
                value=" • ".join(f"`{p}`" for p in report.players),
                inline=False,
            )
        embed.add_field(name="📥 Arrivées / 📤 Départs", value=f"{report.joins} / {report.leaves}", inline=True)
        embed.add_field(name="⚠️ Warnings / 🛑 Erreurs", value=f"{report.warnings} / {report.errors}", inline=True)
        embed.add_field(
            name="ℹ️ Dashboard détaillé indisponible",
            value=(
                "*Ce log ne contient pas d'événements de spawn (spawns, drones, saturation). "
                "Le dashboard complet s'affiche automatiquement quand ils sont présents.*"
            ),
            inline=False,
        )
        embed.add_field(
            name="🔒 Confidentialité",
            value=(
                "*Fichier anonymisé avant analyse : IPs, ports, IDs de compte, adresses MAC "
                "et chemins système supprimés. Rien n'est stocké.*"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyzeCog(bot))
