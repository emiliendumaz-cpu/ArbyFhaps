"""Guide des builds Arbitration : /builds + gestion des builds personnalisés."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage, theme


def _build_embed(build: dict, index: int, total: int) -> discord.Embed:
    embed = theme.make_embed(
        f"⚖️ {build['name']}",
        f"{build['description']}\n{theme.SEPARATOR}",
        color=theme.GOLD,
        footer_extra=f"Build {index + 1}/{total}",
    )
    embed.add_field(name="🤖 Warframe", value=build["frame"], inline=True)
    embed.add_field(name="🏷️ Catégorie", value=build["category"], inline=True)
    if build.get("mods"):
        embed.add_field(name="🧩 Mods", value=build["mods"], inline=False)
    if build.get("arcanes"):
        embed.add_field(name="✨ Arcanes", value=build["arcanes"], inline=False)
    return embed


class BuildsPaginator(discord.ui.View):
    def __init__(self, builds: list[dict]):
        super().__init__(timeout=300)
        self.builds = builds
        self.index = 0

    def current_embed(self) -> discord.Embed:
        return _build_embed(self.builds[self.index], self.index, len(self.builds))

    @discord.ui.button(label="◀ Précédent", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.builds)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)

    @discord.ui.button(label="Suivant ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.builds)
        await interaction.response.edit_message(embed=self.current_embed(), view=self)


class BuildsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _all_builds(self, guild_id: int) -> list[dict]:
        builds = list(storage.load_default_builds())
        builds.extend(storage.load_guild(guild_id).get("builds", []))
        return builds

    @app_commands.command(name="builds", description="Affiche les builds spécial Arbitration.")
    @app_commands.describe(categorie="Filtrer par catégorie (optionnel)")
    async def builds(self, interaction: discord.Interaction, categorie: str | None = None):
        builds = self._all_builds(interaction.guild_id)
        if categorie:
            builds = [b for b in builds if categorie.lower() in b["category"].lower()]
        if not builds:
            await interaction.response.send_message(
                embed=theme.error_embed(f"Aucun build trouvé pour la catégorie « {categorie} »."),
                ephemeral=True,
            )
            return
        view = BuildsPaginator(builds)
        await interaction.response.send_message(embed=view.current_embed(), view=view)

    @builds.autocomplete("categorie")
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = sorted({b["category"] for b in self._all_builds(interaction.guild_id)})
        current_lower = current.lower()
        return [
            app_commands.Choice(name=c, value=c)
            for c in categories
            if current_lower in c.lower()
        ][:25]

    @app_commands.command(name="build-add", description="(Admin) Ajoute un build Arbitration personnalisé au serveur.")
    @app_commands.describe(
        nom="Nom du build",
        frame="Warframe concernée",
        categorie="Catégorie (DPS, Support, Loot…)",
        description="Description / rôle du build",
        mods="Liste des mods (optionnel)",
        arcanes="Arcanes recommandés (optionnel)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def build_add(
        self,
        interaction: discord.Interaction,
        nom: str,
        frame: str,
        categorie: str,
        description: str,
        mods: str | None = None,
        arcanes: str | None = None,
    ):
        data = storage.load_guild(interaction.guild_id)
        data.setdefault("builds", [])
        data["builds"] = [b for b in data["builds"] if b["name"].lower() != nom.lower()]
        data["builds"].append(
            {
                "name": nom,
                "frame": frame,
                "category": categorie,
                "description": description,
                "mods": mods or "",
                "arcanes": arcanes or "",
            }
        )
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(
            embed=theme.make_embed(f"✅ Build ajouté : {nom} ({frame})", color=theme.GREEN)
        )

    @app_commands.command(name="build-remove", description="(Admin) Supprime un build personnalisé du serveur.")
    @app_commands.describe(nom="Nom du build à supprimer")
    @app_commands.default_permissions(manage_guild=True)
    async def build_remove(self, interaction: discord.Interaction, nom: str):
        data = storage.load_guild(interaction.guild_id)
        before = len(data.get("builds", []))
        data["builds"] = [b for b in data.get("builds", []) if b["name"].lower() != nom.lower()]
        if len(data["builds"]) == before:
            await interaction.response.send_message(
                embed=theme.error_embed(
                    f"Build **{nom}** introuvable (les builds par défaut ne peuvent pas être supprimés)."
                ),
                ephemeral=True,
            )
            return
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(
            embed=theme.make_embed(f"🗑️ Build supprimé : {nom}", color=theme.GREEN)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BuildsCog(bot))
