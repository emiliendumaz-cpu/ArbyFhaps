"""Configuration des maps et des compos recommandées par map (par serveur)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, storage, theme, translate


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
        lang = i18n.user_lang(interaction.user.id)
        embed = theme.make_embed(i18n.t(lang, "map.saved", name=nom), color=theme.GREEN)
        embed.add_field(name=i18n.t(lang, "map.mode"), value=mode, inline=True)
        embed.add_field(name=i18n.t(lang, "map.compo"), value=compo, inline=True)
        if notes:
            embed.add_field(name=i18n.t(lang, "map.notes"), value=notes, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="map-remove", description="(Admin) Supprime une map configurée.")
    @app_commands.describe(nom="Nom de la map à supprimer")
    @app_commands.default_permissions(manage_guild=True)
    async def map_remove(self, interaction: discord.Interaction, nom: str):
        lang = i18n.user_lang(interaction.user.id)
        data = storage.load_guild(interaction.guild_id)
        if data["maps"].pop(nom.lower(), None) is None:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "map.notfound", name=nom), lang), ephemeral=True
            )
            return
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(
            embed=theme.make_embed(i18n.t(lang, "map.removed", name=nom), color=theme.GREEN)
        )

    @app_commands.command(name="maps", description="Liste les maps configurées sur ce serveur.")
    async def maps_list(self, interaction: discord.Interaction):
        lang = i18n.user_lang(interaction.user.id)
        data = storage.load_guild(interaction.guild_id)
        if not data["maps"]:
            await interaction.response.send_message(
                embed=theme.make_embed(
                    i18n.t(lang, "map.none.title"),
                    i18n.t(lang, "map.none.desc"),
                    color=theme.BLUE,
                ),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        embed = theme.make_embed(
            i18n.t(lang, "map.list.title"),
            f"{i18n.t(lang, 'map.list.desc')}\n{theme.SEPARATOR}",
            color=theme.GREEN,
            footer_extra=i18n.t(lang, "map.count", n=len(data['maps'])),
        )
        for entry in data["maps"].values():
            mode = await translate.tr(entry["mode"], lang)
            notes = await translate.tr(entry["notes"], lang) if entry["notes"] else ""
            embed.add_field(
                name=f"📍 {entry['nom']} — {mode}",
                value=f"{i18n.t(lang, 'map.compo.label')} {entry['compo']}" + (f"\n📝 {notes}" if notes else ""),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="map", description="Affiche la compo recommandée pour une map.")
    @app_commands.describe(nom="Nom de la map")
    async def map_show(self, interaction: discord.Interaction, nom: str):
        lang = i18n.user_lang(interaction.user.id)
        data = storage.load_guild(interaction.guild_id)
        entry = data["maps"].get(nom.lower())
        if entry is None:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "map.unset", name=nom), lang),
                ephemeral=True,
            )
            return
        await interaction.response.defer(thinking=True)
        mode = await translate.tr(entry["mode"], lang)
        notes = await translate.tr(entry["notes"], lang) if entry["notes"] else ""
        embed = theme.make_embed(f"📍 {entry['nom']} — {mode}", color=theme.GREEN)
        embed.add_field(name=i18n.t(lang, "map.compo.reco"), value=entry["compo"], inline=False)
        if notes:
            embed.add_field(name=i18n.t(lang, "map.notes"), value=notes, inline=False)
        await interaction.followup.send(embed=embed)

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
