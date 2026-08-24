"""Configuration des maps et des compos recommandées par map (par serveur)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage


class MapsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="map-add", description="(Admin) Ajoute ou met à jour une map et sa compo recommandée.")
    @app_commands.describe(
        nom="Nom de la map (ex : Hydron, Casta, Odin…)",
        mode="Mode de mission (ex : Défense, Survie, Interception…)",
        compo="Compo recommandée (ex : Saryn / Wisp / Nekros / Khora)",
        notes="Conseils spécifiques à la map (optionnel)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def map_add(
        self,
        interaction: discord.Interaction,
        nom: str,
        mode: str,
        compo: str,
        notes: str | None = None,
    ):
        data = storage.load_guild(interaction.guild_id)
        data["maps"][nom.lower()] = {
            "nom": nom,
            "mode": mode,
            "compo": compo,
            "notes": notes or "",
        }
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(f"✅ Map **{nom}** enregistrée ({mode}) — compo : {compo}")

    @app_commands.command(name="map-remove", description="(Admin) Supprime une map configurée.")
    @app_commands.describe(nom="Nom de la map à supprimer")
    @app_commands.default_permissions(manage_guild=True)
    async def map_remove(self, interaction: discord.Interaction, nom: str):
        data = storage.load_guild(interaction.guild_id)
        if data["maps"].pop(nom.lower(), None) is None:
            await interaction.response.send_message(f"❌ Map **{nom}** introuvable.", ephemeral=True)
            return
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(f"🗑️ Map **{nom}** supprimée.")

    @app_commands.command(name="maps", description="Liste les maps configurées sur ce serveur.")
    async def maps_list(self, interaction: discord.Interaction):
        data = storage.load_guild(interaction.guild_id)
        if not data["maps"]:
            await interaction.response.send_message(
                "Aucune map configurée. Un admin peut en ajouter avec `/map-add`.", ephemeral=True
            )
            return
        embed = discord.Embed(title="🗺️ Maps configurées", color=discord.Color.green())
        for entry in data["maps"].values():
            embed.add_field(
                name=f"{entry['nom']} — {entry['mode']}",
                value=f"**Compo :** {entry['compo']}" + (f"\n{entry['notes']}" if entry["notes"] else ""),
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="map", description="Affiche la compo recommandée pour une map.")
    @app_commands.describe(nom="Nom de la map")
    async def map_show(self, interaction: discord.Interaction, nom: str):
        data = storage.load_guild(interaction.guild_id)
        entry = data["maps"].get(nom.lower())
        if entry is None:
            await interaction.response.send_message(
                f"❌ Map **{nom}** non configurée. Voir `/maps` pour la liste.", ephemeral=True
            )
            return
        embed = discord.Embed(
            title=f"🗺️ {entry['nom']} — {entry['mode']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Compo recommandée", value=entry["compo"], inline=False)
        if entry["notes"]:
            embed.add_field(name="Notes", value=entry["notes"], inline=False)
        await interaction.response.send_message(embed=embed)

    @map_show.autocomplete("nom")
    @map_remove.autocomplete("nom")
    async def map_name_autocomplete(self, interaction: discord.Interaction, current: str):
        data = storage.load_guild(interaction.guild_id)
        current_lower = current.lower()
        return [
            app_commands.Choice(name=entry["nom"], value=entry["nom"])
            for key, entry in data["maps"].items()
            if current_lower in key
        ][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(MapsCog(bot))
