"""Commande /help : liste de toutes les commandes du bot (localisée)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, theme


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Affiche toutes les commandes du bot.")
    async def help(self, interaction: discord.Interaction):
        lang = i18n.user_lang(interaction.user.id)
        embed = theme.make_embed(
            i18n.t(lang, "h.title"),
            f"{i18n.t(lang, 'h.desc')}\n{theme.SEPARATOR}",
            color=theme.BLUE,
        )
        for section in ("analyse", "maps", "builds", "tracker", "misc"):
            embed.add_field(
                name=i18n.t(lang, f"h.{section}.name"),
                value=i18n.t(lang, f"h.{section}.value"),
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
