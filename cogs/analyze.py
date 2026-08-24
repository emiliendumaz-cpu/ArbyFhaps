"""Commande /analyse : analyse d'un EE.log uploadé, avec anonymisation."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import eelog


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
                "❌ Fichier trop volumineux (max 30 Mo).", ephemeral=True
            )
            return

        name_lower = fichier.filename.lower()
        if not (name_lower.endswith(".log") or name_lower.endswith(".txt")):
            await interaction.response.send_message(
                "❌ Merci d'envoyer un fichier `.log` ou `.txt` (le fichier EE.log de Warframe).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = (await fichier.read()).decode("utf-8", errors="replace")
        report = eelog.parse(raw)
        del raw  # le contenu brut n'est jamais conservé

        embed = discord.Embed(
            title="📊 Analyse du run",
            color=discord.Color.gold() if report.is_arbitration else discord.Color.blurple(),
            description=(
                "🔒 *Fichier anonymisé avant analyse : IPs, ports, IDs de compte, "
                "adresses MAC et chemins système supprimés. Rien n'est stocké.*"
            ),
        )
        embed.add_field(name="Mission", value=report.mission or "Non détectée", inline=False)
        embed.add_field(name="Type", value="⚖️ Arbitration" if report.is_arbitration else "Mission standard", inline=True)
        embed.add_field(name="Durée de session", value=report.duration_text, inline=True)
        embed.add_field(name="Migrations d'hôte", value=str(report.host_migrations), inline=True)

        if report.players:
            embed.add_field(name="Joueurs détectés (pseudos en jeu)", value=", ".join(report.players), inline=False)
        embed.add_field(name="Arrivées / départs d'escouade", value=f"{report.joins} / {report.leaves}", inline=True)
        embed.add_field(name="Warnings / Erreurs moteur", value=f"{report.warnings} / {report.errors}", inline=True)
        embed.set_footer(text=f"{report.lines} lignes analysées")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyzeCog(bot))
