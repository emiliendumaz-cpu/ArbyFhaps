"""Cog /map : configuration des maps d'arbitration et de leurs compos recommandées."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import storage

MISSION_TYPES = ["Défense", "Interception", "Survie", "Excavation", "Défense mobile", "Disruption"]


class Maps(commands.Cog):
    group = app_commands.Group(name="map", description="Maps d'arbitration et compos recommandées")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _load() -> dict:
        return storage.load("maps")

    @staticmethod
    def _save(data: dict) -> None:
        storage.save("maps", data)

    async def _autocomplete_map(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        maps = self._load()
        current = current.lower()
        return [
            app_commands.Choice(name=name.title(), value=name)
            for name in maps
            if current in name.lower()
        ][:25]

    # --------------------------------------------------------------- commands

    @group.command(name="liste", description="Liste toutes les maps configurées.")
    async def liste(self, interaction: discord.Interaction):
        maps = self._load()
        if not maps:
            await interaction.response.send_message(
                "Aucune map configurée. Ajoutez-en une avec `/map definir`.", ephemeral=True
            )
            return

        embed = discord.Embed(title="🗺️ Maps d'arbitration configurées", color=discord.Color.teal())
        for name, info in sorted(maps.items()):
            compo = ", ".join(info.get("compo", [])) or "—"
            embed.add_field(
                name=f"{name.title()} — {info.get('type', '?')}",
                value=f"Compo : {compo}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)

    @group.command(name="info", description="Affiche la compo recommandée pour une map.")
    @app_commands.describe(nom="Nom de la map")
    @app_commands.autocomplete(nom=_autocomplete_map)
    async def info(self, interaction: discord.Interaction, nom: str):
        maps = self._load()
        info = maps.get(nom.lower())
        if info is None:
            await interaction.response.send_message(
                f"❌ Map `{nom}` inconnue. Voir `/map liste`.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🗺️ {nom.title()}",
            color=discord.Color.teal(),
            description=info.get("notes") or None,
        )
        embed.add_field(name="Type", value=info.get("type", "?"), inline=True)
        compo = info.get("compo", [])
        embed.add_field(
            name="Compo recommandée",
            value="\n".join(f"{i + 1}. {frame}" for i, frame in enumerate(compo)) or "—",
            inline=True,
        )
        await interaction.response.send_message(embed=embed)

    @group.command(name="definir", description="Ajoute ou modifie une map et sa compo (admin).")
    @app_commands.describe(
        nom="Nom de la map (ex: Casta (Ceres))",
        type_mission="Type de mission",
        compo="Warframes recommandées, séparées par des virgules (ex: Vauban, Wisp, Octavia, Khora)",
        notes="Conseils / remarques (optionnel)",
    )
    @app_commands.choices(
        type_mission=[app_commands.Choice(name=t, value=t) for t in MISSION_TYPES]
    )
    @app_commands.default_permissions(manage_guild=True)
    async def definir(
        self,
        interaction: discord.Interaction,
        nom: str,
        type_mission: app_commands.Choice[str],
        compo: str,
        notes: str | None = None,
    ):
        frames = [f.strip() for f in compo.split(",") if f.strip()]
        if not frames:
            await interaction.response.send_message(
                "❌ La compo est vide. Exemple : `Vauban, Wisp, Octavia, Khora`.", ephemeral=True
            )
            return
        if len(frames) > 4:
            await interaction.response.send_message(
                "❌ Une escouade compte 4 joueurs maximum.", ephemeral=True
            )
            return

        maps = self._load()
        maps[nom.lower()] = {
            "type": type_mission.value,
            "compo": frames,
            "notes": notes or "",
        }
        self._save(maps)
        await interaction.response.send_message(
            f"✅ Map **{nom.title()}** ({type_mission.value}) enregistrée avec la compo : "
            f"{', '.join(frames)}."
        )

    @group.command(name="supprimer", description="Supprime une map configurée (admin).")
    @app_commands.describe(nom="Nom de la map à supprimer")
    @app_commands.autocomplete(nom=_autocomplete_map)
    @app_commands.default_permissions(manage_guild=True)
    async def supprimer(self, interaction: discord.Interaction, nom: str):
        maps = self._load()
        if maps.pop(nom.lower(), None) is None:
            await interaction.response.send_message(f"❌ Map `{nom}` inconnue.", ephemeral=True)
            return
        self._save(maps)
        await interaction.response.send_message(f"🗑️ Map **{nom.title()}** supprimée.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Maps(bot))
