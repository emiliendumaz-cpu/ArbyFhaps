"""
Cog builds :
  /builds           — guide des builds avec menu par catégorie (tout le monde)
  /build definir    — ajoute ou modifie un build (admin)
  /build supprimer  — supprime un build (admin)
  /build categories — liste les catégories existantes
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import i18n, storage


def _load_builds() -> dict:
    return storage.load("builds")


def _save_builds(data: dict) -> None:
    storage.save("builds", data)


def _category_embed(category: str, entries: list[dict], lang: str) -> discord.Embed:
    embed = discord.Embed(
        title=i18n.t("b.cat_title", lang, cat=category),
        color=discord.Color.gold(),
    )
    total = len(embed.title)
    for i, entry in enumerate(entries):
        lines = []
        if entry.get("description"):
            lines.append(entry["description"])
        if entry.get("mods") and entry["mods"] != "—":
            lines.append(i18n.t("b.mods_label", lang, mods=entry["mods"]))
        if entry.get("conseils"):
            lines.append(f"💡 {entry['conseils']}")
        name = entry.get("nom", "Build")
        value = "\n".join(lines)[:1024]
        # Limite Discord : 6000 caractères par embed. On s'arrête avant.
        if total + len(name) + len(value) > 5800:
            embed.set_footer(text=i18n.t("b.overflow", lang, n=len(entries) - i))
            break
        embed.add_field(name=name, value=value, inline=False)
        total += len(name) + len(value)
    if not entries:
        embed.description = i18n.t("b.cat_empty", lang)
    return embed


class CategorySelect(discord.ui.Select):
    def __init__(self, builds: dict, current: str, lang: str):
        options = [
            discord.SelectOption(label=cat, default=(cat == current))
            for cat in list(builds)[:25]
        ]
        super().__init__(placeholder=i18n.t("b.placeholder", lang), options=options)

    async def callback(self, interaction: discord.Interaction):
        # Chaque joueur qui clique voit les messages d'erreur dans SA langue ;
        # l'embed partagé garde la langue de celui qui a lancé /builds.
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        builds = _load_builds()
        category = self.values[0]
        if category not in builds:
            await interaction.response.send_message(i18n.t("b.cat_gone", lang), ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=_category_embed(category, builds[category], lang),
            view=BuildsView(builds, category, lang),
        )


class BuildsView(discord.ui.View):
    def __init__(self, builds: dict, current: str, lang: str):
        super().__init__(timeout=600)
        self.add_item(CategorySelect(builds, current, lang))


# ---------------------------------------------------------------------------
# Autocomplétion partagée
# ---------------------------------------------------------------------------

async def _autocomplete_categorie(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    current = current.lower()
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in _load_builds()
        if current in cat.lower()
    ][:25]


async def _autocomplete_build(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    # La catégorie déjà saisie dans la commande restreint les propositions.
    categorie = getattr(interaction.namespace, "categorie", None)
    builds = _load_builds()
    entries = builds.get(categorie, []) if categorie in builds else [
        e for cat_entries in builds.values() for e in cat_entries
    ]
    current = current.lower()
    return [
        app_commands.Choice(name=e["nom"], value=e["nom"])
        for e in entries
        if current in e.get("nom", "").lower()
    ][:25]


class Builds(commands.Cog):
    group = app_commands.Group(
        name="build",
        description="Gestion des builds du guide (/builds pour consulter)",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------ consultation

    @app_commands.command(
        name="builds",
        description="Guide des builds arbitration / Arbitration builds guide.",
    )
    async def builds(self, interaction: discord.Interaction):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        builds = _load_builds()
        if not builds:
            await interaction.response.send_message(i18n.t("b.none", lang), ephemeral=True)
            return

        first_category = next(iter(builds))
        await interaction.response.send_message(
            embed=_category_embed(first_category, builds[first_category], lang),
            view=BuildsView(builds, first_category, lang),
        )

    # --------------------------------------------------------------- gestion

    @group.command(name="definir", description="Ajoute ou modifie un build (même nom = mise à jour).")
    @app_commands.describe(
        categorie="Catégorie (existante ou nouvelle, ex: Warframes)",
        nom="Nom du build (ex: Octavia)",
        description="Ce que fait le build / son rôle",
        mods="Liste des mods, séparés par des virgules",
        conseils="Astuces d'utilisation (optionnel)",
    )
    @app_commands.autocomplete(categorie=_autocomplete_categorie, nom=_autocomplete_build)
    async def definir(
        self,
        interaction: discord.Interaction,
        categorie: str,
        nom: str,
        description: str,
        mods: str,
        conseils: str | None = None,
    ):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        builds = _load_builds()
        categorie = categorie.strip()
        nom = nom.strip()
        if not categorie or not nom:
            await interaction.response.send_message(i18n.t("b.empty_fields", lang), ephemeral=True)
            return

        entries = builds.setdefault(categorie, [])
        entry = {
            "nom": nom,
            "description": description.strip(),
            "mods": mods.strip(),
            "conseils": (conseils or "").strip(),
        }
        for i, existing in enumerate(entries):
            if existing.get("nom", "").lower() == nom.lower():
                entries[i] = entry
                message = i18n.t("b.saved_mod", lang, nom=nom, cat=categorie)
                break
        else:
            if len(entries) >= 25:
                await interaction.response.send_message(i18n.t("b.full", lang), ephemeral=True)
                return
            entries.append(entry)
            message = i18n.t("b.saved_add", lang, nom=nom, cat=categorie)

        _save_builds(builds)
        await interaction.response.send_message(
            message, embed=_category_embed(categorie, entries, lang)
        )

    @group.command(name="supprimer", description="Supprime un build du guide.")
    @app_commands.describe(categorie="Catégorie du build", nom="Nom du build à supprimer")
    @app_commands.autocomplete(categorie=_autocomplete_categorie, nom=_autocomplete_build)
    async def supprimer(self, interaction: discord.Interaction, categorie: str, nom: str):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        builds = _load_builds()
        entries = builds.get(categorie)
        if entries is None:
            await interaction.response.send_message(
                i18n.t("b.unknown_cat", lang, cat=categorie), ephemeral=True
            )
            return

        remaining = [e for e in entries if e.get("nom", "").lower() != nom.strip().lower()]
        if len(remaining) == len(entries):
            await interaction.response.send_message(
                i18n.t("b.not_found", lang, nom=nom, cat=categorie), ephemeral=True
            )
            return

        if remaining:
            builds[categorie] = remaining
        else:
            # Une catégorie vide disparaît du menu de /builds.
            del builds[categorie]
        _save_builds(builds)
        await interaction.response.send_message(i18n.t("b.deleted", lang, nom=nom, cat=categorie))

    @group.command(name="categories", description="Liste les catégories et le nombre de builds.")
    async def categories(self, interaction: discord.Interaction):
        lang = i18n.get_lang(interaction.user.id, interaction.locale)
        builds = _load_builds()
        if not builds:
            await interaction.response.send_message(i18n.t("b.cats_none", lang), ephemeral=True)
            return
        lines = [
            i18n.t("b.cat_line", lang, cat=cat, n=len(entries))
            for cat, entries in builds.items()
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Builds(bot))
