"""Guide des builds Arbitration.

Les mods ne sont jamais retranscrits en texte : chaque fiche porte la capture
d'écran du build (rangs et polarités compris), attachée via /build-image.

 - /build <warframe> [variante] : menu déroulant des warframes, puis variante
   proposée en autocomplétion selon la warframe choisie (ex. Cyte-09 → Shock,
   Sunder, Nourish, Smite, EM ; Jade/Nokko/Nidus → Pre)
 - /builds [catégorie] : catalogue complet, navigation ◀ ▶
 - /build-add, /build-image, /build-remove : gestion par les admins

Chaque build peut avoir une image (capture d'écran du build en jeu) stockée
dans data/build_images/ — uploadée par un admin via /build-image.
"""

from __future__ import annotations

import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, storage, theme, translate

IMAGES_DIR = Path(__file__).resolve().parent.parent / "data" / "build_images"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
MAX_IMAGE_BYTES = 8 * 1024 * 1024

# Warframes proposées dans le menu déroulant de /build
FRAMES = [
    "Wisp", "Cyte-09", "Citrine", "Volt", "Rhino", "Saryn",
    "Mirage", "Vauban", "Jade", "Nokko", "Nidus",
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _key(build: dict) -> str:
    """Identité d'un build : warframe + variante, sinon son nom."""
    frame, variant = build.get("frame", ""), build.get("variant", "")
    if frame and variant:
        return f"{frame.lower()}|{variant.lower()}"
    return build["name"].lower()


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


async def _build_embed(build: dict, index: int, total: int, lang: str = "fr") -> tuple[discord.Embed, discord.File | None]:
    # Textes rédigés à la main : traduits vers la langue de l'utilisateur
    # (les mods/arcanes sont des noms propres, jamais traduits)
    description = await translate.tr(build["description"], lang)
    category = await translate.tr(build["category"], lang)
    shards = await translate.tr(build.get("shards"), lang)
    embed = theme.make_embed(
        f"⚖️ {build['name']}",
        f"{description}\n{theme.SEPARATOR}",
        color=theme.GOLD,
        footer_extra=i18n.t(lang, "b.footer", i=index + 1, n=total),
    )
    embed.add_field(name=i18n.t(lang, "b.frame"), value=build["frame"], inline=True)
    if build.get("variant"):
        embed.add_field(name=i18n.t(lang, "b.variant"), value=build["variant"], inline=True)
    embed.add_field(name=i18n.t(lang, "b.cat"), value=category, inline=True)

    # Les mods sont portés par la capture d'écran, jamais retranscrits en texte :
    # elle montre aussi les rangs et les polarités. Tant qu'elle manque, on le dit.
    path = _image_path(build)
    if path is None and build.get("category") != "Général":
        embed.add_field(name=i18n.t(lang, "b.mods"), value=i18n.t(lang, "b.mods.pending"), inline=False)
    if build.get("arcanes"):
        embed.add_field(name=i18n.t(lang, "b.arcanes"), value=build["arcanes"], inline=False)
    if shards:
        embed.add_field(name=i18n.t(lang, "b.shards"), value=shards, inline=False)

    file = None
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
        self.message: discord.Message | None = None
        self.previous.label = i18n.t(lang, "b.prev")
        self.next.label = i18n.t(lang, "b.next")

    async def on_timeout(self):
        # Boutons expirés : on les retire au lieu de laisser des clics en échec
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass

    async def current(self) -> tuple[discord.Embed, discord.File | None]:
        return await _build_embed(self.builds[self.index], self.index, len(self.builds), self.lang)

    async def _flip(self, interaction: discord.Interaction, step: int):
        self.index = (self.index + step) % len(self.builds)
        await interaction.response.defer()
        embed, file = await self.current()
        await interaction.edit_original_response(
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
        """Builds par défaut, ceux du serveur écrasant les fiches de même
        warframe + variante (ou de même nom)."""
        merged: dict[str, dict] = {_key(b): b for b in storage.load_default_builds()}
        for b in storage.load_guild(guild_id).get("builds", []):
            merged[_key(b)] = b
        return list(merged.values())

    def _frame_builds(self, guild_id: int, frame: str) -> list[dict]:
        return [b for b in self._all_builds(guild_id)
                if b.get("frame", "").lower() == frame.lower()]

    async def _send_builds(self, interaction: discord.Interaction, builds: list[dict], lang: str):
        """Une fiche seule, ou un paginateur si plusieurs."""
        await interaction.response.defer(thinking=True)
        if len(builds) == 1:
            embed, file = await _build_embed(builds[0], 0, 1, lang)
            await interaction.followup.send(embed=embed, **({"file": file} if file else {}))
            return
        view = BuildsPaginator(builds, lang)
        embed, file = await view.current()
        kwargs = {"file": file} if file else {}
        view.message = await interaction.followup.send(embed=embed, view=view, wait=True, **kwargs)

    # ------------------------------------------------------------------
    # /build : menu déroulant warframe + variante dépendante
    # ------------------------------------------------------------------

    @app_commands.command(name="build", description="Affiche le build d'une warframe pour l'Arbitration.")
    @app_commands.describe(
        warframe="La warframe",
        variante="La variante du build (dépend de la warframe choisie)",
    )
    @app_commands.choices(warframe=[app_commands.Choice(name=f, value=f) for f in FRAMES])
    async def build(self, interaction: discord.Interaction, warframe: str, variante: str | None = None):
        lang = i18n.user_lang(interaction.user.id)
        builds = self._frame_builds(interaction.guild_id, warframe)
        if not builds:
            await interaction.response.send_message(
                embed=theme.error_embed(i18n.t(lang, "b.frame.none", frame=warframe), lang),
                ephemeral=True,
            )
            return

        if variante:
            matching = [b for b in builds if b.get("variant", "").lower() == variante.lower()]
            if not matching:
                available = ", ".join(f"`{b['variant']}`" for b in builds if b.get("variant")) or "—"
                await interaction.response.send_message(
                    embed=theme.error_embed(
                        i18n.t(lang, "b.variant.none", variant=variante, frame=warframe, list=available),
                        lang,
                    ),
                    ephemeral=True,
                )
                return
            builds = matching

        await self._send_builds(interaction, builds, lang)

    @build.autocomplete("variante")
    async def build_variant_autocomplete(self, interaction: discord.Interaction, current: str):
        # La warframe déjà saisie dans la commande filtre les variantes proposées
        frame = getattr(interaction.namespace, "warframe", None)
        if not frame:
            return []
        current_lower = current.lower()
        seen, choices = set(), []
        for b in self._frame_builds(interaction.guild_id, frame):
            variant = b.get("variant")
            if not variant or variant.lower() in seen:
                continue
            if current_lower and current_lower not in variant.lower():
                continue
            seen.add(variant.lower())
            choices.append(app_commands.Choice(name=variant, value=variant))
        return choices[:25]

    # ------------------------------------------------------------------
    # /builds : catalogue complet
    # ------------------------------------------------------------------

    @app_commands.command(name="builds", description="Affiche tous les builds spécial Arbitration.")
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
        await self._send_builds(interaction, builds, lang)

    @builds.autocomplete("categorie")
    async def category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = sorted({b["category"] for b in self._all_builds(interaction.guild_id)})
        current_lower = current.lower()
        return [
            app_commands.Choice(name=c, value=c)
            for c in categories
            if current_lower in c.lower()
        ][:25]

    # ------------------------------------------------------------------
    # Gestion (admins)
    # ------------------------------------------------------------------

    @app_commands.command(name="build-image", description="(Admin) Attache une capture d'écran à un build (affichée dans /build).")
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

    @app_commands.command(name="build-add", description="(Admin) Ajoute ou remplace un build Arbitration.")
    @app_commands.describe(
        frame="Warframe (choisissez dans la liste pour qu'elle apparaisse dans /build)",
        variante="Variante du build (ex : Shock, Sunder, Pre…)",
        nom="Nom affiché de la fiche",
        categorie="Catégorie (DPS, Support, Loot…)",
        description="Description / rôle du build",
        arcanes="Arcanes recommandés (optionnel)",
        shards="Éclats d'Archonte (optionnel)",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def build_add(
        self,
        interaction: discord.Interaction,
        frame: str,
        variante: str,
        nom: str,
        categorie: str,
        description: str,
        arcanes: str | None = None,
        shards: str | None = None,
    ):
        entry = {
            "name": nom,
            "frame": frame,
            "variant": variante,
            "category": categorie,
            "description": description,
            "arcanes": arcanes or "",
            "shards": shards or "",
        }
        data = storage.load_guild(interaction.guild_id)
        data.setdefault("builds", [])
        # Remplace la fiche de même warframe + variante (ou de même nom)
        data["builds"] = [b for b in data["builds"] if _key(b) != _key(entry)]
        data["builds"].append(entry)
        storage.save_guild(interaction.guild_id, data)

        lang = i18n.user_lang(interaction.user.id)
        await interaction.response.send_message(
            embed=theme.make_embed(
                i18n.t(lang, "b.added", name=nom, frame=f"{frame} · {variante}"),
                i18n.t(lang, "b.added.hint"),
                color=theme.GREEN,
            )
        )

    @build_add.autocomplete("frame")
    async def frame_autocomplete(self, interaction: discord.Interaction, current: str):
        current_lower = current.lower()
        return [
            app_commands.Choice(name=f, value=f)
            for f in FRAMES
            if current_lower in f.lower()
        ][:25]

    @build_add.autocomplete("variante")
    async def build_add_variant_autocomplete(self, interaction: discord.Interaction, current: str):
        frame = getattr(interaction.namespace, "frame", None)
        if not frame:
            return []
        return await self.build_variant_autocomplete(interaction, current)

    @app_commands.command(name="build-remove", description="(Admin) Supprime un build ajouté sur ce serveur.")
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

    @build_remove.autocomplete("nom")
    async def guild_build_autocomplete(self, interaction: discord.Interaction, current: str):
        current_lower = current.lower()
        return [
            app_commands.Choice(name=b["name"], value=b["name"])
            for b in storage.load_guild(interaction.guild_id).get("builds", [])
            if current_lower in b["name"].lower()
        ][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(BuildsCog(bot))
