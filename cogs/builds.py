"""Cog /builds : guide des builds spécial arbitration, avec menu par catégorie."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage


def _load_builds() -> dict:
    return storage.load("builds")


def _category_embed(category: str, entries: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title=f"📘 Builds Arbitration — {category}",
        color=discord.Color.gold(),
    )
    for entry in entries:
        lines = []
        if entry.get("description"):
            lines.append(entry["description"])
        if entry.get("mods") and entry["mods"] != "—":
            lines.append(f"**Mods :** {entry['mods']}")
        if entry.get("conseils"):
            lines.append(f"💡 {entry['conseils']}")
        embed.add_field(name=entry.get("nom", "Build"), value="\n".join(lines)[:1024], inline=False)
    return embed


class CategorySelect(discord.ui.Select):
    def __init__(self, builds: dict, current: str):
        options = [
            discord.SelectOption(label=cat, default=(cat == current))
            for cat in builds
        ]
        super().__init__(placeholder="Choisir une catégorie…", options=options)
        self.builds = builds

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        view = BuildsView(self.builds, category)
        await interaction.response.edit_message(
            embed=_category_embed(category, self.builds[category]), view=view
        )


class BuildsView(discord.ui.View):
    def __init__(self, builds: dict, current: str):
        super().__init__(timeout=600)
        self.add_item(CategorySelect(builds, current))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Builds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="builds",
        description="Guide des builds spécial arbitration (Warframes, armes, compagnons…).",
    )
    async def builds(self, interaction: discord.Interaction):
        builds = _load_builds()
        if not builds:
            await interaction.response.send_message(
                "❌ Aucun build configuré (fichier `data/builds.json` vide ou manquant).",
                ephemeral=True,
            )
            return

        first_category = next(iter(builds))
        await interaction.response.send_message(
            embed=_category_embed(first_category, builds[first_category]),
            view=BuildsView(builds, first_category),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Builds(bot))
