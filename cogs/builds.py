"""Guide des builds Arbitration : /builds + gestion des builds personnalisés.

Chaque build peut avoir une image (capture d'écran du build en jeu) stockée
dans data/build_images/ — uploadée par un admin via /build-image.
"""

from __future__ import annotations

import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, storage, theme

IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "build_images"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _image_path(build: dict) -> Path | None:
    """Image du build : champ « image » explicite, sinon <slug-du-nom>.<ext>."""
    candidates = []
    explicit = build.get("image")
    if explicit:
        candidates.append(Path(explicit).name)  # jamais de chemin, juste le nom
    slug = _slug(build["name"])
    candidates.extend(f"{slug}{ext}" for ext in IMAGE_EXTS)
    for name in candidates:
        path = IMAGES_DIR / name
        if path.is_file():
            return path
    return None


def _build_embed(build: dict, index: int, total: int, lang: str = "fr") -> tuple[discord.Embed, discord.File | None]:
    embed = theme.make_embed(
        f"⚖️ {build['name']}",
        f"{build['description']}\n{theme.SEPARATOR}",
        color=theme.GOLD,
        footer_extra=i18n.t(lang, "b.footer", i=index + 1, n=total),
    )
    embed.add_field(name=i18n.t(lang, "b.frame"), value=build["frame"], inline=True)
    embed.add_field(name=i18n.t(lang, "b.cat"), value=build["category"], inline=True)
    if build.get("mods"):
        embed.add_field(name=i18n.t(lang, "b.mods"), value=build["mods"], inline=False)
    if build.get("arcanes"):
        embed.add_field(name=i18n.t(lang, "b.arcanes"), value=build["arcanes"], inline=False)
    if build.get("shards"):
        embed.add_field(name=i18n.t(lang, "b.shards"), value=build["shards"], inline=False)

    file = None
    path = _image_path(build)
    if path:
        file = discord.File(path, filename=path.name)
        embed.set_image(url=f"attachment://{path.name}")
    return embed, file


class BuildsPaginator(discord.ui.View):
    def __init__(self, builds: list[dict], lang: str = "fr"):
        super().__init__(timeout=300)
        self.builds = builds
        self.lang = lang
        self.index = 0
        self.previous.label = i18n.t(lang, "b.prev")
        self.next.label = i18n.t(lang, "b.next")

    def current(self) -> tuple[discord.Embed, discord.File | None]:
        return _build_embed(self.builds[self.index], self.index, len(self.builds), self.lang)

    async def _flip(self, interaction: discord.Interaction, step: int):
        self.index = (self.index + step) % len(self.builds)
        embed, file = self.current()
        await interaction.response.edit_message(
            embed=embed, view=self, attachments=[file] if file else []
        )

    @discord.ui.button(label="◀ Précédent", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._flip(interaction, -1)

    @discord.ui.button(label="Suivant ▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._flip(interaction, 1)


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
        lang = i18n.user_lang(interaction.user.id)
        builds = self._all_builds(interaction.guild_id)
        if categorie:
            builds = [b for b in builds if categorie.lower() in b["category"].lower()]
        if not builds:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.nocat", cat=categorie), lang),
                ephemeral=True,
            )
            return
        view = BuildsPaginator(builds, lang)
        embed, file = view.current()
        if file:
            await interaction.response.send_message(embed=embed, view=view, file=file)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    @builds.autocomplete("categorie")
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = sorted({b["category"] for b in self._all_builds(interaction.guild_id)})
        current_lower = current.lower()
        return [
            app_commands.Choice(name=c, value=c)
            for c in categories
            if current_lower in c.lower()
        ][:25]

    @app_commands.command(name="build-image", description="(Admin) Attache une capture d'écran à un build (affichée dans /builds).")
    @app_commands.describe(nom="Nom du build (autocomplétion)", fichier="Capture d'écran (png/jpg/webp, max 8 Mo)")
    @app_commands.default_permissions(manage_guild=True)
    async def build_image(self, interaction: discord.Interaction, nom: str, fichier: discord.Attachment):
        lang = i18n.user_lang(interaction.user.id)
        build = next(
            (b for b in self._all_builds(interaction.guild_id) if b["name"].lower() == nom.lower()),
            None,
        )
        if build is None:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.img.notfound", name=nom), lang), ephemeral=True
            )
            return
        ext = Path(fichier.filename).suffix.lower()
        if ext not in IMAGE_EXTS:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.img.badfmt"), lang), ephemeral=True
            )
            return
        if fichier.size > MAX_IMAGE_BYTES:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.img.toobig"), lang), ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        # Le champ « image » explicite du build prime : on écrit sous ce nom-là
        target_name = Path(build["image"]).name if build.get("image") else f"{_slug(build['name'])}{ext}"
        target = IMAGES_DIR / target_name
        # Purge les anciennes variantes du slug pour éviter les doublons d'extension
        for old_ext in IMAGE_EXTS:
            old = IMAGES_DIR / f"{_slug(build['name'])}{old_ext}"
            if old != target and old.is_file():
                old.unlink()
        await fichier.save(target)

        embed = theme.make_embed(
            i18n.t(lang, "b.img.saved", name=build['name']),
            i18n.t(lang, "b.img.saved.desc"),
            color=theme.GREEN,
        )
        file = discord.File(target, filename=target.name)
        embed.set_image(url=f"attachment://{target.name}")
        await interaction.followup.send(embed=embed, file=file)

    @build_image.autocomplete("nom")
    async def build_name_autocomplete(self, interaction: discord.Interaction, current: str):
        current_lower = current.lower()
        return [
            app_commands.Choice(name=b["name"], value=b["name"])
            for b in self._all_builds(interaction.guild_id)
            if current_lower in b["name"].lower()
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
        lang = i18n.user_lang(interaction.user.id)
        await interaction.response.send_message(
            embed=theme.make_embed(
                i18n.t(lang, "b.added", name=nom, frame=frame),
                i18n.t(lang, "b.added.hint"),
                color=theme.GREEN,
            )
        )

    @app_commands.command(name="build-remove", description="(Admin) Supprime un build personnalisé du serveur.")
    @app_commands.describe(nom="Nom du build à supprimer")
    @app_commands.default_permissions(manage_guild=True)
    async def build_remove(self, interaction: discord.Interaction, nom: str):
        lang = i18n.user_lang(interaction.user.id)
        data = storage.load_guild(interaction.guild_id)
        before = len(data.get("builds", []))
        data["builds"] = [b for b in data.get("builds", []) if b["name"].lower() != nom.lower()]
        if len(data["builds"]) == before:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.notfound", name=nom), lang),
                ephemeral=True,
            )
            return
        storage.save_guild(interaction.guild_id, data)
        await interaction.response.send_message(
            embed=theme.make_embed(i18n.t(lang, "b.removed", name=nom), color=theme.GREEN)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(BuildsCog(bot))
