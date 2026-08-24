"""Commande /help : liste de toutes les commandes du bot."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import theme


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Affiche toutes les commandes du bot.")
    async def help(self, interaction: discord.Interaction):
        embed = theme.make_embed(
            "📖 Commandes d'ArbyFhaps",
            "Le bot Arbitration de votre serveur : analyse de runs, maps et builds.\n"
            f"{theme.SEPARATOR}",
            color=theme.BLUE,
        )
        embed.add_field(
            name="📊 Analyse de run",
            value=(
                "`/analyse` — Analysez votre fichier `EE.log` "
                "(`%LOCALAPPDATA%\\Warframe\\EE.log`).\n"
                "🔒 IPs, IDs et données perso supprimés automatiquement, rien n'est stocké."
            ),
            inline=False,
        )
        embed.add_field(
            name="🗺️ Maps & compos",
            value=(
                "`/map <nom>` — Compo recommandée pour une map\n"
                "`/maps` — Liste des maps configurées\n"
                "`/map-add` 🔧 — Ajouter/mettre à jour une map\n"
                "`/map-remove` 🔧 — Supprimer une map"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚖️ Builds Arbitration",
            value=(
                "`/builds [categorie]` — Guide des builds (navigation ◀ ▶)\n"
                "`/build-add` 🔧 — Ajouter un build personnalisé\n"
                "`/build-remove` 🔧 — Supprimer un build personnalisé"
            ),
            inline=False,
        )
        embed.add_field(
            name="ℹ️ Divers",
            value="`/help` — Cette aide\n🔧 = réservé aux admins (permission « Gérer le serveur »)",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
