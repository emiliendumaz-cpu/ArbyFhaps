"""Commande /language : langue des réponses du bot, par utilisateur."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, theme


class LanguageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="language", description="Choisir la langue du bot (pour vous uniquement). / Pick the bot's language (just for you).")
    @app_commands.describe(langue="Votre langue / Your language")
    @app_commands.choices(langue=[app_commands.Choice(name=label, value=code) for code, label in i18n.LANGS.items()])
    async def language(self, interaction: discord.Interaction, langue: str):
        i18n.set_user_lang(interaction.user.id, langue)
        embed = theme.make_embed(
            i18n.t(langue, "lang.set"),
            i18n.t(langue, "lang.note"),
            color=theme.GREEN,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LanguageCog(bot))
