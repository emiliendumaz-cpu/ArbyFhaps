"""Cog /langue : chaque joueur choisit la langue dans laquelle le bot lui répond."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n


class Langue(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="langue",
        description="Choisis la langue du bot / Choose the bot's language.",
    )
    @app_commands.describe(langue="Ta langue / Your language")
    @app_commands.choices(
        langue=[
            app_commands.Choice(name="Français", value="fr"),
            app_commands.Choice(name="English", value="en"),
            app_commands.Choice(name="Auto (langue Discord / Discord language)", value="auto"),
        ]
    )
    async def langue(self, interaction: discord.Interaction, langue: app_commands.Choice[str]):
        if langue.value == "auto":
            i18n.set_lang(interaction.user.id, None)
            lang = i18n.get_lang(interaction.user.id, interaction.locale)
            message = i18n.t("lang.auto", lang)
        else:
            i18n.set_lang(interaction.user.id, langue.value)
            message = i18n.t("lang.set", langue.value, lang=i18n.LANGS[langue.value])
        # Réponse éphémère : le choix de langue ne concerne que le joueur.
        await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Langue(bot))
