"""
Cog /arby : suivi dynamique de l'arbitration en cours (style Altair).

  /arby actuelle — affiche l'arbitration en cours (tout le monde)
  /arby suivre   — poste un message dynamique dans le salon, actualisé
                   automatiquement à chaque rotation d'arbitration (admin)
  /arby stop     — arrête le suivi sur ce serveur (admin)

Source : l'API communautaire https://api.warframestat.us (worldstate PC).
Le message suivi est édité uniquement quand l'arbitration change ; le
compte à rebours, lui, est un timestamp Discord qui défile tout seul
côté client, sans édition.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import datetime, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import i18n, storage

log = logging.getLogger("arbyfhaps.arby")

API_URL = "https://api.warframestat.us/pc/arbitration"
_STORE = "arby"  # data/arby.json : {guild_id: {channel_id, message_id, lang}}

# L'arbitration tourne toutes les heures ; on vérifie toutes les 2 minutes
# pour capter la rotation vite sans marteler l'API.
CHECK_SECONDS = 120


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _find_configured_map(node: str, maps: dict) -> tuple[str, dict] | None:
    """Retrouve la map configurée correspondant au nœud de l'API (accents ignorés)."""
    wanted = _strip_accents(node).lower().strip()
    for name, info in maps.items():
        if _strip_accents(name).lower().strip() == wanted:
            return name, info
    return None


def render_embed(data: dict | None, lang: str, maps: dict) -> discord.Embed:
    """Construit l'embed d'arbitration. `data` est le JSON de l'API (ou None)."""
    if not data or not data.get("node"):
        return discord.Embed(
            title=i18n.t("arby.title", lang),
            description=i18n.t("arby.unavailable", lang),
            color=discord.Color.dark_grey(),
        )

    node = data["node"]
    configured = _find_configured_map(node, maps)
    embed = discord.Embed(
        title=i18n.t("arby.title", lang),
        color=discord.Color.gold() if configured else discord.Color.dark_teal(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name=i18n.t("an.f_node", lang), value=node, inline=True)
    embed.add_field(
        name=i18n.t("an.f_type", lang),
        value=data.get("type") or "?",
        inline=True,
    )
    if data.get("enemy"):
        embed.add_field(name=i18n.t("arby.f_enemy", lang), value=data["enemy"], inline=True)

    expiry = _parse_iso(data.get("expiry"))
    if expiry:
        ts = int(expiry.timestamp())
        # <t:..:R> défile côté client : pas besoin d'éditer le message pour ça.
        embed.add_field(
            name=i18n.t("arby.f_rotation", lang),
            value=f"<t:{ts}:R> (<t:{ts}:t>)",
            inline=True,
        )

    if data.get("archwing"):
        embed.add_field(name="🪽", value=i18n.t("arby.archwing", lang), inline=True)

    if configured:
        name, info = configured
        compo = ", ".join(info.get("compo", [])) or "—"
        value = i18n.t("arby.meta_compo", lang, compo=compo)
        if info.get("notes"):
            value += f"\n💡 {info['notes']}"
        embed.add_field(name=i18n.t("arby.meta_map", lang, nom=name.title()), value=value[:1024], inline=False)
    else:
        embed.add_field(
            name=i18n.t("arby.not_meta_title", lang),
            value=i18n.t("arby.not_meta", lang),
            inline=False,
        )

    embed.set_footer(text=i18n.t("arby.footer", lang))
    return embed


class Arby(commands.Cog):
    group = app_commands.Group(name="arby", description="Arbitration en cours (suivi dynamique)")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        # Clé de la dernière arbitration vue (nœud + expiration) pour ne
        # rééditer les messages suivis que lors d'une vraie rotation.
        self._last_key: str | None = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15),
            headers={"User-Agent": "ArbyFhaps Discord bot"},
        )
        self.refresh_loop.start()

    async def cog_unload(self):
        self.refresh_loop.cancel()
        if self.session:
            await self.session.close()

    # ----------------------------------------------------------------- API

    async def fetch_arbitration(self, lang: str) -> dict | None:
        """Récupère l'arbitration en cours ; None si l'API est indisponible."""
        try:
            async with self.session.get(API_URL, params={"language": lang}) as resp:
                if resp.status != 200:
                    log.warning("API arbitration : HTTP %s", resp.status)
                    return None
                data = await resp.json()
                return data if isinstance(data, dict) else None
        except (aiohttp.ClientError, TimeoutError) as exc:
            log.warning("API arbitration injoignable : %s", exc)
            return None

    # ---------------------------------------------------------------- boucle

    @tasks.loop(seconds=CHECK_SECONDS)
    async def refresh_loop(self):
        trackers = storage.load(_STORE)
        if not trackers:
            return

        data = await self.fetch_arbitration("en")
        if not data or not data.get("node"):
            return  # API en carafe : on garde le dernier message affiché

        key = f"{data.get('node')}|{data.get('expiry')}"
        if key == self._last_key:
            return  # pas de rotation depuis le dernier passage
        # (au premier passage après démarrage, _last_key est None : on édite
        # toujours, le message stocké peut dater d'avant le redémarrage)
        self._last_key = key

        maps = storage.load("maps")
        # On ne re-télécharge par langue que si un suivi l'utilise.
        payloads: dict[str, dict | None] = {"en": data}
        changed = False
        for guild_id, info in list(trackers.items()):
            lang = info.get("lang", "fr")
            if lang not in payloads:
                payloads[lang] = await self.fetch_arbitration(lang)
            payload = payloads[lang] or data  # repli sur l'anglais
            embed = render_embed(payload, lang, maps)

            channel = self.bot.get_channel(info["channel_id"])
            if channel is None:
                trackers.pop(guild_id)
                changed = True
                continue
            try:
                message = channel.get_partial_message(info["message_id"])
                await message.edit(embed=embed)
            except discord.NotFound:
                # Message supprimé à la main : on arrête ce suivi.
                trackers.pop(guild_id)
                changed = True
            except discord.HTTPException as exc:
                log.warning("Édition du suivi %s impossible : %s", guild_id, exc)

        if changed:
            storage.save(_STORE, trackers)

    @refresh_loop.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------- commands

    @group.command(name="actuelle", description="Affiche l'arbitration en cours.")
    async def actuelle(self, interaction: discord.Interaction):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        await interaction.response.defer()
        data = await self.fetch_arbitration(lang)
        embed = render_embed(data, lang, storage.load("maps"))
        await interaction.followup.send(embed=embed)

    @group.command(
        name="suivre",
        description="Poste un message dynamique actualisé à chaque rotation d'arbitration (admin).",
    )
    @app_commands.describe(langue="Langue du message dynamique (défaut : français)")
    @app_commands.choices(
        langue=[
            app_commands.Choice(name="Français", value="fr"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def suivre(
        self,
        interaction: discord.Interaction,
        langue: app_commands.Choice[str] | None = None,
    ):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        # Permission vérifiée à la main : le groupe /arby reste ouvert à tous
        # pour /arby actuelle, Discord ne permet pas de le régler par sous-commande.
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(i18n.t("arby.need_admin", lang), ephemeral=True)
            return

        embed_lang = langue.value if langue else "fr"
        await interaction.response.defer()
        data = await self.fetch_arbitration(embed_lang)
        embed = render_embed(data, embed_lang, storage.load("maps"))
        message = await interaction.followup.send(embed=embed, wait=True)

        trackers = storage.load(_STORE)
        trackers[str(interaction.guild_id)] = {
            "channel_id": message.channel.id,
            "message_id": message.id,
            "lang": embed_lang,
        }
        storage.save(_STORE, trackers)
        # Force la réédition au prochain passage de la boucle.
        self._last_key = None
        await interaction.followup.send(i18n.t("arby.tracking_started", lang), ephemeral=True)

    @group.command(name="stop", description="Arrête le suivi dynamique sur ce serveur (admin).")
    async def stop(self, interaction: discord.Interaction):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(i18n.t("arby.need_admin", lang), ephemeral=True)
            return

        trackers = storage.load(_STORE)
        if trackers.pop(str(interaction.guild_id), None) is None:
            await interaction.response.send_message(i18n.t("arby.no_tracking", lang), ephemeral=True)
            return
        storage.save(_STORE, trackers)
        await interaction.response.send_message(i18n.t("arby.tracking_stopped", lang))


async def setup(bot: commands.Bot):
    await bot.add_cog(Arby(bot))
