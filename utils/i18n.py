"""
Internationalisation du bot.

Chaque joueur choisit sa langue avec /langue ; sans choix explicite, la langue
du client Discord du joueur est utilisée (anglais si non francophone… par
défaut : français, c'est un bot d'arbitration français quand même).

Les préférences sont stockées dans data/langues.json : {user_id: "fr"|"en"}.
"""

from __future__ import annotations

from utils import storage

DEFAULT_LANG = "fr"
LANGS = {"fr": "Français", "en": "English"}

_STORE = "langues"


# ---------------------------------------------------------------------------
# Préférences par joueur
# ---------------------------------------------------------------------------

def get_lang(user_id: int, discord_locale: object = None) -> str:
    """Langue effective d'un joueur : préférence explicite, sinon locale Discord."""
    prefs = storage.load(_STORE)
    lang = prefs.get(str(user_id))
    if lang in LANGS:
        return lang
    # Pas de préférence : on suit la langue du client Discord.
    locale = str(discord_locale or "").lower()
    if locale.startswith("fr"):
        return "fr"
    if locale.startswith("en"):
        return "en"
    return DEFAULT_LANG


def set_lang(user_id: int, lang: str | None) -> None:
    """Enregistre la préférence d'un joueur ; None = retour au mode auto."""
    prefs = storage.load(_STORE)
    if lang is None:
        prefs.pop(str(user_id), None)
    elif lang in LANGS:
        prefs[str(user_id)] = lang
    else:
        raise ValueError(f"Langue inconnue : {lang!r}")
    storage.save(_STORE, prefs)


# ---------------------------------------------------------------------------
# Traductions
# ---------------------------------------------------------------------------

STRINGS: dict[str, dict[str, str]] = {
    # --- /langue ---
    "lang.set": {
        "fr": "✅ Langue définie sur **{lang}**. Le bot te répondra désormais en français.",
        "en": "✅ Language set to **{lang}**. The bot will now answer you in English.",
    },
    "lang.auto": {
        "fr": "✅ Mode auto : le bot suivra la langue de ton client Discord.",
        "en": "✅ Auto mode: the bot will follow your Discord client language.",
    },

    # --- /analyse ---
    "an.too_big": {
        "fr": "❌ Fichier trop volumineux ({size:.1f} Mo, max {max} Mo). Astuce : relance Warframe avant ta run pour repartir d'un log vide.",
        "en": "❌ File too large ({size:.1f} MB, max {max} MB). Tip: restart Warframe before your run to start from a fresh log.",
    },
    "an.bad_ext": {
        "fr": "❌ Merci d'envoyer un fichier `.log` ou `.txt` (normalement `EE.log`).",
        "en": "❌ Please upload a `.log` or `.txt` file (normally `EE.log`).",
    },
    "an.dl_fail": {
        "fr": "❌ Impossible de télécharger le fichier, réessaie.",
        "en": "❌ Could not download the file, please try again.",
    },
    "an.title": {"fr": "📊 Analyse de run", "en": "📊 Run analysis"},
    "an.title_arby": {"fr": " — Arbitration ✅", "en": " — Arbitration ✅"},
    "an.privacy": {
        "fr": "🔒 Toutes les données sensibles (IP, identifiants, chemins système) ont été supprimées avant l'analyse. Le fichier n'est pas conservé.",
        "en": "🔒 All sensitive data (IPs, account IDs, system paths) was stripped before analysis. The file is not kept.",
    },
    "an.footer": {"fr": "Demandé par {name}", "en": "Requested by {name}"},
    "an.f_node": {"fr": "Nœud", "en": "Node"},
    "an.f_type": {"fr": "Type de mission", "en": "Mission type"},
    "an.f_duration": {"fr": "Durée", "en": "Duration"},
    "an.f_squad": {"fr": "Escouade", "en": "Squad"},
    "an.f_frames": {"fr": "Warframes détectées", "en": "Detected Warframes"},
    "an.f_end": {"fr": "Fin de mission", "en": "Mission end"},
    "an.f_notes": {"fr": "Remarques", "en": "Notes"},
    "an.not_detected": {"fr": "Non détecté", "en": "Not detected"},
    "an.unknown": {"fr": "Inconnue", "en": "Unknown"},
    "an.end_yes": {"fr": "✅ Détectée", "en": "✅ Detected"},
    "an.end_no": {"fr": "❓ Non détectée", "en": "❓ Not detected"},
    "an.note_est_duration": {
        "fr": "Durée estimée sur l'ensemble du log (début de mission non détecté).",
        "en": "Duration estimated over the whole log (mission start not detected).",
    },
    "an.note_not_arby": {
        "fr": "Aucun marqueur d'arbitration détecté — ce log ne semble pas provenir d'une arbitration (ou le format a changé).",
        "en": "No arbitration marker found — this log does not seem to come from an arbitration (or the format changed).",
    },
    "an.note_migrations": {
        "fr": "⚠️ {n} migration(s) d'hôte détectée(s) — certaines données peuvent être incomplètes.",
        "en": "⚠️ {n} host migration(s) detected — some data may be incomplete.",
    },
    "an.note_no_end": {
        "fr": "Fin de mission non détectée (log coupé ou mission en cours).",
        "en": "Mission end not detected (truncated log or mission still running).",
    },

    # --- types de mission ---
    "mt.MT_SURVIVAL": {"fr": "Survie", "en": "Survival"},
    "mt.MT_DEFENSE": {"fr": "Défense", "en": "Defense"},
    "mt.MT_INTERCEPTION": {"fr": "Interception", "en": "Interception"},
    "mt.MT_EXCAVATE": {"fr": "Excavation", "en": "Excavation"},
    "mt.MT_ARTIFACT": {"fr": "Défense mobile", "en": "Mobile Defense"},
    "mt.MT_TERRITORY": {"fr": "Interception", "en": "Interception"},
    "mt.MT_DISRUPTION": {"fr": "Disruption", "en": "Disruption"},
    "mt.MT_ENDLESS_EXTERMINATION": {"fr": "Extermination sans fin", "en": "Endless Extermination"},

    # --- /map ---
    "map.none": {
        "fr": "Aucune map configurée. Ajoutez-en une avec `/map definir`.",
        "en": "No map configured. Add one with `/map definir`.",
    },
    "map.list_title": {"fr": "🗺️ Maps d'arbitration configurées", "en": "🗺️ Configured arbitration maps"},
    "map.compo_line": {"fr": "Compo : {compo}", "en": "Squad: {compo}"},
    "map.unknown": {
        "fr": "❌ Map `{nom}` inconnue. Voir `/map liste`.",
        "en": "❌ Unknown map `{nom}`. See `/map liste`.",
    },
    "map.f_type": {"fr": "Type", "en": "Type"},
    "map.f_compo": {"fr": "Compo recommandée", "en": "Recommended squad"},
    "map.empty_compo": {
        "fr": "❌ La compo est vide. Exemple : `Vauban, Wisp, Octavia, Khora`.",
        "en": "❌ Squad is empty. Example: `Vauban, Wisp, Octavia, Khora`.",
    },
    "map.too_many": {
        "fr": "❌ Une escouade compte 4 joueurs maximum.",
        "en": "❌ A squad has at most 4 players.",
    },
    "map.saved": {
        "fr": "✅ Map **{nom}** ({type}) enregistrée avec la compo : {compo}.",
        "en": "✅ Map **{nom}** ({type}) saved with squad: {compo}.",
    },
    "map.deleted": {"fr": "🗑️ Map **{nom}** supprimée.", "en": "🗑️ Map **{nom}** deleted."},
    "map.unknown_simple": {"fr": "❌ Map `{nom}` inconnue.", "en": "❌ Unknown map `{nom}`."},

    # --- /builds & /build ---
    "b.none": {
        "fr": "❌ Aucun build configuré. Ajoutez-en avec `/build definir`.",
        "en": "❌ No build configured. Add some with `/build definir`.",
    },
    "b.cat_title": {"fr": "📘 Builds Arbitration — {cat}", "en": "📘 Arbitration builds — {cat}"},
    "b.cat_empty": {"fr": "Aucun build dans cette catégorie.", "en": "No build in this category."},
    "b.cat_gone": {"fr": "❌ Cette catégorie n'existe plus.", "en": "❌ This category no longer exists."},
    "b.placeholder": {"fr": "Choisir une catégorie…", "en": "Pick a category…"},
    "b.overflow": {
        "fr": "… et {n} autre(s) build(s) — catégorie trop pleine pour tout afficher.",
        "en": "… and {n} more build(s) — category too full to display everything.",
    },
    "b.mods_label": {"fr": "**Mods :** {mods}", "en": "**Mods:** {mods}"},
    "b.empty_fields": {
        "fr": "❌ Catégorie et nom ne peuvent pas être vides.",
        "en": "❌ Category and name cannot be empty.",
    },
    "b.full": {
        "fr": "❌ Cette catégorie contient déjà 25 builds (limite d'affichage Discord).",
        "en": "❌ This category already holds 25 builds (Discord display limit).",
    },
    "b.saved_add": {
        "fr": "✅ Build **{nom}** ajouté dans la catégorie **{cat}**.",
        "en": "✅ Build **{nom}** added to category **{cat}**.",
    },
    "b.saved_mod": {
        "fr": "✅ Build **{nom}** modifié dans la catégorie **{cat}**.",
        "en": "✅ Build **{nom}** updated in category **{cat}**.",
    },
    "b.unknown_cat": {"fr": "❌ Catégorie `{cat}` inconnue.", "en": "❌ Unknown category `{cat}`."},
    "b.not_found": {
        "fr": "❌ Build `{nom}` introuvable dans **{cat}**.",
        "en": "❌ Build `{nom}` not found in **{cat}**.",
    },
    "b.deleted": {
        "fr": "🗑️ Build **{nom}** supprimé de **{cat}**.",
        "en": "🗑️ Build **{nom}** deleted from **{cat}**.",
    },
    "b.cats_none": {"fr": "Aucun build configuré.", "en": "No build configured."},
    "b.cat_line": {"fr": "• **{cat}** — {n} build(s)", "en": "• **{cat}** — {n} build(s)"},
}


def t(key: str, lang: str, **kwargs) -> str:
    """Traduit une clé dans la langue demandée (repli : français, puis la clé)."""
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    return text.format(**kwargs) if kwargs else text


def mission_type(mtype: str | None, lang: str) -> str:
    """Nom traduit d'un type de mission interne (MT_*), ou valeur brute."""
    if not mtype:
        return t("an.not_detected", lang)
    entry = STRINGS.get(f"mt.{mtype}")
    return entry.get(lang, mtype) if entry else mtype
