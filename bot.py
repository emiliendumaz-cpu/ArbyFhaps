"""ArbyFhaps — Bot Discord pour l'Arbitration Warframe.

Fonctionnalités :
 - /analyse : analyse d'un EE.log uploadé (anonymisé : aucune IP ni donnée perso)
 - /map-add, /map-remove, /maps, /map : maps et compos recommandées par serveur
 - /builds, /build-add, /build-remove : guide des builds Arbitration
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

COGS = ["cogs.analyze", "cogs.maps", "cogs.builds", "cogs.help", "cogs.tracker", "cogs.language"]


class ArbyBot(commands.Bot):
    def __init__(self):
        # Aucun intent privilégié requis : uniquement des slash commands.
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)

        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        logging.info("Connecté en tant que %s (%s serveurs)", self.user, len(self.guilds))


def main():
    try:
        import deep_translator  # noqa: F401
    except ImportError:
        logging.warning(
            "deep-translator est absent : la traduction automatique des textes est DÉSACTIVÉE. "
            "Lancez le bot via start.bat ou exécutez : pip install -r requirements.txt"
        )
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN manquant : copiez .env.example vers .env et renseignez votre token.")
    asyncio.run(ArbyBot().start(token))


if __name__ == "__main__":
    main()
