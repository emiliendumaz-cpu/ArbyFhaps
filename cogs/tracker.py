"""Suivi des arbitrations : message auto-actualisé + note F → S.

/tracker-start installe dans le salon un message que le bot édite toutes les
5 minutes : arbitration en cours (avec compte à rebours) et, quand la source
de prédictions répond, les prochaines arbitrations. /tier-set permet à chaque
serveur d'ajuster la note d'un nœud.
"""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils import storage, theme, worldstate

log = logging.getLogger(__name__)

REFRESH_MINUTES = 5


def _fmt_line(arby: worldstate.Arbitration, tier: str) -> str:
    line = f"{worldstate.TIER_EMOJI[tier]} **{tier}** — **{arby.node}** · {arby.mission_type}"
    if arby.enemy:
        line += f" ({arby.enemy})"
    return line


class TrackerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self._last_render: dict[int, str] = {}  # guild_id -> empreinte du dernier contenu

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        self.refresh.start()

    async def cog_unload(self):
        self.refresh.cancel()
        if self.session:
            await self.session.close()

    # ------------------------------------------------------------------
    # Construction de l'embed
    # ------------------------------------------------------------------

    async def _build_embed(self, guild_id: int) -> tuple[discord.Embed, str]:
        overrides = storage.load_guild(guild_id).get("tiers", {})
        current = await worldstate.fetch_current(self.session)
        schedule_current, upcoming = await worldstate.fetch_schedule(self.session)
        if current is None:
            current = schedule_current  # repli : planning communautaire

        embed = theme.make_embed(
            "⚖️ Suivi des Arbitrations",
            f"Notation communautaire de **F** à **S** (ajustable avec `/tier-set`).\n{theme.SEPARATOR}",
            color=theme.GOLD,
            footer_extra=f"Actualisé toutes les {REFRESH_MINUTES} min",
        )

        fingerprint_parts: list[str] = []

        if current:
            tier = worldstate.rate(current, overrides)
            value = _fmt_line(current, tier)
            if current.expiry:
                value += f"\n⏳ Se termine <t:{int(current.expiry.timestamp())}:R>"
            embed.add_field(name="🔥 En cours", value=value, inline=False)
            fingerprint_parts.append(f"{current.node}|{tier}")
        else:
            embed.add_field(
                name="🔥 En cours",
                value="*Donnée momentanément indisponible (sources muettes ou non résolues). "
                      "Réessai automatique dans quelques minutes — un admin peut lancer `/sources` "
                      "pour diagnostiquer.*",
                inline=False,
            )
            fingerprint_parts.append("none")

        if upcoming:
            lines = []
            for arby in upcoming:
                tier = worldstate.rate(arby, overrides)
                when = f"<t:{int(arby.activation.timestamp())}:t> · " if arby.activation else ""
                lines.append(f"{when}{_fmt_line(arby, tier)}")
                fingerprint_parts.append(f"{arby.node}|{tier}")
            embed.add_field(name="🗓️ À venir", value="\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="🗓️ À venir",
                value="*Prédictions indisponibles pour le moment.*",
                inline=False,
            )

        return embed, "|".join(fingerprint_parts)

    # ------------------------------------------------------------------
    # Boucle d'actualisation
    # ------------------------------------------------------------------

    @tasks.loop(minutes=REFRESH_MINUTES)
    async def refresh(self):
        for guild_id in storage.all_guild_ids():
            data = storage.load_guild(guild_id)
            tracker = data.get("tracker")
            if not tracker:
                continue
            try:
                await self._update_tracker_message(guild_id, data, tracker)
            except Exception:
                log.exception("Échec d'actualisation du tracker pour %s", guild_id)

    @refresh.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    async def _update_tracker_message(self, guild_id: int, data: dict, tracker: dict):
        channel = self.bot.get_channel(tracker["channel_id"])
        if channel is None:
            return

        embed, fingerprint = await self._build_embed(guild_id)
        if self._last_render.get(guild_id) == fingerprint:
            return  # rien de neuf : pas d'édition inutile
        try:
            message = await channel.fetch_message(tracker["message_id"])
            await message.edit(embed=embed)
        except discord.NotFound:
            # Message supprimé : on le republie et on mémorise le nouvel ID
            message = await channel.send(embed=embed)
            tracker["message_id"] = message.id
            storage.save_guild(guild_id, data)
        except discord.Forbidden:
            log.warning("Permissions manquantes pour le tracker dans %s", guild_id)
            return
        self._last_render[guild_id] = fingerprint

    # ------------------------------------------------------------------
    # Commandes
    # ------------------------------------------------------------------

    @app_commands.command(name="arbitration", description="Affiche l'arbitration en cours et les prochaines, notées de F à S.")
    async def arbitration(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        embed, _ = await self._build_embed(interaction.guild_id)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tracker-start", description="(Admin) Installe le message auto-actualisé des arbitrations dans ce salon.")
    @app_commands.default_permissions(manage_guild=True)
    async def tracker_start(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        embed, fingerprint = await self._build_embed(interaction.guild_id)
        message = await interaction.channel.send(embed=embed)
        data = storage.load_guild(interaction.guild_id)
        data["tracker"] = {"channel_id": interaction.channel_id, "message_id": message.id}
        storage.save_guild(interaction.guild_id, data)
        self._last_render[interaction.guild_id] = fingerprint
        await interaction.followup.send(
            embed=theme.make_embed(
                "✅ Tracker installé",
                f"Le message sera actualisé toutes les {REFRESH_MINUTES} minutes. "
                "Épinglez-le pour le retrouver facilement !",
                color=theme.GREEN,
            ),
            ephemeral=True,
        )

    @app_commands.command(name="tracker-stop", description="(Admin) Arrête le message auto-actualisé des arbitrations.")
    @app_commands.default_permissions(manage_guild=True)
    async def tracker_stop(self, interaction: discord.Interaction):
        data = storage.load_guild(interaction.guild_id)
        tracker = data.pop("tracker", None)
        if tracker is None:
            await interaction.response.send_message(
                embed=theme.error_embed("Aucun tracker actif sur ce serveur."), ephemeral=True
            )
            return
        storage.save_guild(interaction.guild_id, data)
        self._last_render.pop(interaction.guild_id, None)
        channel = self.bot.get_channel(tracker["channel_id"])
        if channel:
            try:
                message = await channel.fetch_message(tracker["message_id"])
                await message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        await interaction.response.send_message(
            embed=theme.make_embed("🗑️ Tracker arrêté", color=theme.GREEN), ephemeral=True
        )

    @app_commands.command(name="sources", description="(Admin) Diagnostique les sources de données d'arbitration.")
    @app_commands.default_permissions(manage_guild=True)
    async def sources(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        results = await worldstate.probe_sources(self.session)
        embed = theme.make_embed(
            "🩺 Diagnostic des sources",
            "Copiez ce résultat pour ajuster le connecteur si une source a changé de format.",
            color=theme.BLUE,
        )
        for name, url, verdict in results:
            embed.add_field(name=name, value=f"`{url}`\n```{verdict[:900]}```", inline=False)
        summary = await worldstate.inspect_schedule(self.session)
        embed.add_field(name="🧠 Planning interprété par le bot", value=f"```{summary[:1000]}```", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="tier-set", description="(Admin) Fixe la note (F à S) d'un nœud pour ce serveur.")
    @app_commands.describe(node="Nœud, tel qu'affiché par le tracker (ex : Casta (Ceres))", tier="Note")
    @app_commands.choices(tier=[app_commands.Choice(name=t, value=t) for t in worldstate.TIER_ORDER])
    @app_commands.default_permissions(manage_guild=True)
    async def tier_set(self, interaction: discord.Interaction, node: str, tier: str):
        data = storage.load_guild(interaction.guild_id)
        data.setdefault("tiers", {})[node.lower()] = tier
        storage.save_guild(interaction.guild_id, data)
        self._last_render.pop(interaction.guild_id, None)  # force la prochaine édition
        await interaction.response.send_message(
            embed=theme.make_embed(
                f"✅ {worldstate.TIER_EMOJI[tier]} {node} noté {tier}",
                "La note sera appliquée à la prochaine actualisation du tracker.",
                color=theme.GREEN,
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TrackerCog(bot))
