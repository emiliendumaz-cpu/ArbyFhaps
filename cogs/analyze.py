"""Commande /analyse : analyse d'un EE.log uploadé, avec anonymisation."""

from __future__ import annotations

import asyncio
import io

import discord
from discord import app_commands
from discord.ext import commands

from utils import dashboard, eelog, i18n, theme


class AnalyzeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="analyse",
        description="Analyse un fichier EE.log de Warframe (IPs et données perso supprimées automatiquement).",
    )
    @app_commands.describe(
        fichier="Votre fichier EE.log (Windows : %LOCALAPPDATA%\\Warframe\\EE.log)",
        vitus="Vitus Essence obtenues sur ce run (recommandé : le log ne les compte pas de façon fiable)",
        drones="Drones d'Arbitration tués, si vous connaissez le compte exact",
        chance="Chance de drop par drone en %, selon vos boosters (défaut : 36)",
    )
    async def analyse(
        self,
        interaction: discord.Interaction,
        fichier: discord.Attachment,
        vitus: app_commands.Range[int, 0, 100000] | None = None,
        drones: app_commands.Range[int, 1, 100000] | None = None,
        chance: app_commands.Range[float, 0.1, 100.0] | None = None,
    ):
        lang = i18n.user_lang(interaction.user.id)

        if fichier.size > eelog.MAX_LOG_BYTES:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "an.too_big"), lang), ephemeral=True
            )
            return

        name_lower = fichier.filename.lower()
        if not (name_lower.endswith(".log") or name_lower.endswith(".txt")):
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "an.bad_ext"), lang), ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        raw = (await fichier.read()).decode("utf-8", errors="replace")
        report = eelog.parse(raw)
        del raw  # le contenu brut n'est jamais conservé
        eelog.apply_overrides(report, vitus=vitus, drones=drones)
        drop_chance = (chance / 100) if chance else dashboard.VITUS_DROP_CHANCE

        # Log riche (ou compte de drones fourni) → dashboard image
        if report.has_spawn_data or drones:
            png = await asyncio.to_thread(dashboard.render, report, drop_chance)
            file = discord.File(io.BytesIO(png), filename="analyse-arbitration.png")
            embed = theme.make_embed(
                i18n.t(lang, "an.title"),
                i18n.t(lang, "an.privacy"),
                color=theme.GOLD if report.is_arbitration else theme.BLUE,
                footer_extra=i18n.t(lang, "an.lines", n=report.lines),
            )
            if report.players:
                embed.add_field(
                    name=i18n.t(lang, "an.players"),
                    value=" • ".join(f"`{p}`" for p in report.players),
                    inline=False,
                )
            if vitus is None:
                embed.add_field(
                    name=i18n.t(lang, "an.vitus.hint.title"),
                    value=i18n.t(lang, "an.vitus.hint"),
                    inline=False,
                )
            embed.set_image(url="attachment://analyse-arbitration.png")
            await interaction.followup.send(embed=embed, file=file)
            return

        is_arby = report.is_arbitration
        embed = theme.make_embed(
            i18n.t(lang, "an.title"),
            f"{i18n.t(lang, 'an.arby') if is_arby else i18n.t(lang, 'an.std')}\n{theme.SEPARATOR}",
            color=theme.GOLD if is_arby else theme.BLUE,
            footer_extra=i18n.t(lang, "an.lines", n=report.lines),
        )
        embed.add_field(name=i18n.t(lang, "an.mission"),
                        value=report.mission or i18n.t(lang, "an.not_detected"), inline=True)
        embed.add_field(name=i18n.t(lang, "an.duration"), value=report.duration_text, inline=True)
        embed.add_field(name=i18n.t(lang, "an.migrations"), value=str(report.host_migrations), inline=True)

        if report.players:
            embed.add_field(
                name=i18n.t(lang, "an.players"),
                value=" • ".join(f"`{p}`" for p in report.players),
                inline=False,
            )
        embed.add_field(name=i18n.t(lang, "an.joins"), value=f"{report.joins} / {report.leaves}", inline=True)
        embed.add_field(name=i18n.t(lang, "an.warnerr"), value=f"{report.warnings} / {report.errors}", inline=True)
        embed.add_field(name=i18n.t(lang, "an.nodash.title"), value=i18n.t(lang, "an.nodash"), inline=False)
        embed.add_field(name=i18n.t(lang, "an.privacy.title"), value=i18n.t(lang, "an.privacy"), inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AnalyzeCog(bot))
