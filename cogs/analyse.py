"""Cog /analyse : analyse anonymisée d'un fichier EE.log uploadé."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import eelog, i18n


class Analyse(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="analyse",
        description="Analyse une run depuis ton EE.log / Analyze a run from your EE.log.",
    )
    @app_commands.describe(fichier="Ton fichier EE.log (dans %LOCALAPPDATA%/Warframe/)")
    async def analyse(self, interaction: discord.Interaction, fichier: discord.Attachment):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        # L'analyse peut prendre quelques secondes sur un gros log.
        await interaction.response.defer(ephemeral=False)

        if fichier.size > eelog.MAX_LOG_BYTES:
            await interaction.followup.send(
                i18n.t(
                    "an.too_big", lang,
                    size=fichier.size / 1024 / 1024,
                    max=eelog.MAX_LOG_BYTES // 1024 // 1024,
                )
            )
            return

        filename = (fichier.filename or "").lower()
        if not (filename.endswith(".log") or filename.endswith(".txt")):
            await interaction.followup.send(i18n.t("an.bad_ext", lang))
            return

        try:
            raw_bytes = await fichier.read()
        except discord.HTTPException:
            await interaction.followup.send(i18n.t("an.dl_fail", lang))
            return

        # Décodage + anonymisation + analyse, tout en mémoire. Le contenu brut
        # est libéré aussitôt : rien n'est conservé ni écrit sur disque.
        text = eelog.decode_log_bytes(raw_bytes)
        del raw_bytes
        report = eelog.parse_log(text)
        del text

        embed = self._build_embed(report, interaction.user, lang)
        await interaction.followup.send(embed=embed)

    def _build_embed(
        self, report: eelog.RunReport, user: discord.abc.User, lang: str
    ) -> discord.Embed:
        color = discord.Color.gold() if report.is_arbitration else discord.Color.blurple()
        title = i18n.t("an.title", lang)
        if report.is_arbitration:
            title += i18n.t("an.title_arby", lang)
        embed = discord.Embed(
            title=title,
            color=color,
            description=i18n.t("an.privacy", lang),
        )
        embed.set_footer(text=i18n.t("an.footer", lang, name=user.display_name))

        not_detected = i18n.t("an.not_detected", lang)
        embed.add_field(
            name=i18n.t("an.f_node", lang),
            value=report.mission_node or not_detected,
            inline=True,
        )
        embed.add_field(
            name=i18n.t("an.f_type", lang),
            value=i18n.mission_type(report.mission_type, lang),
            inline=True,
        )
        embed.add_field(
            name=i18n.t("an.f_duration", lang),
            value=report.duration_text or i18n.t("an.unknown", lang),
            inline=True,
        )

        embed.add_field(
            name=i18n.t("an.f_squad", lang),
            value="\n".join(f"• {p}" for p in report.players) if report.players else not_detected,
            inline=True,
        )
        embed.add_field(
            name=i18n.t("an.f_frames", lang),
            value=", ".join(report.warframes) if report.warframes else not_detected,
            inline=True,
        )
        embed.add_field(
            name=i18n.t("an.f_end", lang),
            value=i18n.t("an.end_yes" if report.ended_properly else "an.end_no", lang),
            inline=True,
        )

        if report.notes:
            embed.add_field(
                name=i18n.t("an.f_notes", lang),
                value="\n".join(f"– {i18n.t(key, lang, **params)}" for key, params in report.notes),
                inline=False,
            )

        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Analyse(bot))
