"""
ArbyFhaps — bot Discord dédié aux arbitrations Warframe.

Commandes :
  /analyse  — analyse anonymisée d'un fichier EE.log uploadé
  /map …    — maps configurées et compos recommandées
  /builds   — guide des builds spécial arbitration

Lancement :
  1. cp .env.example .env  (et remplir DISCORD_TOKEN)
  2. pip install -r requirements.txt
  3. python bot.py
"""

from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("arbyfhaps")

COGS = ["cogs.analyse", "cogs.maps", "cogs.builds", "cogs.langue", "cogs.arby"]

# Le bot n'a besoin d'aucun intent privilégié : pas de lecture des messages,
# pas de liste de membres. Les slash commands suffisent.
intents = discord.Intents.default()


class ArbyFhaps(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)

    async def setup_hook(self):
        for cog in COGS:
            await self.load_extension(cog)
            log.info("Cog chargé : %s", cog)

        guild_id = os.getenv("GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Commandes synchronisées sur le serveur %s", guild_id)
        else:
            await self.tree.sync()
            log.info("Commandes synchronisées globalement (propagation : jusqu'à ~1h)")

    async def on_ready(self):
        log.info("Connecté en tant que %s (id=%s)", self.user, self.user.id)


def main():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "votre_token_ici":
        raise SystemExit(
            "DISCORD_TOKEN manquant : copiez .env.example vers .env et remplissez le token."
        )
    ArbyFhaps().run(token)


if __name__ == "__main__":
    main()
