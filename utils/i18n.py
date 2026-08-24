"""Internationalisation par utilisateur.

Chaque utilisateur choisit sa langue avec /language ; elle est stockée dans
data/users.json et s'applique aux réponses que le bot LUI adresse. Les
contenus rédigés par les admins (descriptions de builds, notes de maps)
restent dans leur langue d'origine.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT = "fr"
LANGS = {"fr": "Français 🇫🇷", "en": "English 🇬🇧", "no": "Norsk 🇳🇴"}

_USERS_FILE = Path(__file__).resolve().parent.parent / "data" / "users.json"


def user_lang(user_id: int) -> str:
    try:
        with _USERS_FILE.open(encoding="utf-8") as f:
            return json.load(f).get(str(user_id), {}).get("lang", DEFAULT)
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULT


def set_user_lang(user_id: int, lang: str) -> None:
    try:
        with _USERS_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data.setdefault(str(user_id), {})["lang"] = lang
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def t(lang: str, key: str, **kwargs) -> str:
    entry = _CATALOG.get(key)
    if entry is None:
        return key
    text = entry.get(lang) or entry[DEFAULT]
    return text.format(**kwargs) if kwargs else text


_CATALOG: dict[str, dict[str, str]] = {
    # ----- /language -----
    "lang.set": {
        "fr": "✅ Langue réglée sur **Français** — les réponses du bot vous parleront désormais français.",
        "en": "✅ Language set to **English** — the bot will now answer you in English.",
        "no": "✅ Språk satt til **norsk** — boten svarer deg nå på norsk.",
    },
    "lang.note": {
        "fr": "Ce réglage ne concerne que vous. Les textes rédigés par les admins (builds, maps) sont traduits automatiquement — seuls les noms de mods, d'arcanes et de frames restent en l'état.",
        "en": "This setting only affects you. Admin-written content (builds, maps) is translated automatically — only mod, arcane and frame names stay as-is.",
        "no": "Denne innstillingen gjelder bare deg. Innhold skrevet av admins (builds, kart) oversettes automatisk — bare navn på mods, arcanes og frames beholdes som de er.",
    },
    # ----- Générique -----
    "err.title": {"fr": "❌ Oups", "en": "❌ Oops", "no": "❌ Oi"},
    # ----- /analyse -----
    "an.too_big": {"fr": "Fichier trop volumineux (max 30 Mo).", "en": "File too large (max 30 MB).", "no": "Filen er for stor (maks 30 MB)."},
    "an.bad_ext": {
        "fr": "Merci d'envoyer un fichier `.log` ou `.txt` (le fichier EE.log de Warframe).",
        "en": "Please upload a `.log` or `.txt` file (Warframe's EE.log).",
        "no": "Last opp en `.log`- eller `.txt`-fil (Warframes EE.log).",
    },
    "an.title": {"fr": "📊 Analyse du run", "en": "📊 Run analysis", "no": "📊 Analyse av runden"},
    "an.privacy": {
        "fr": "🔒 *Fichier anonymisé avant analyse : IPs, ports, IDs de compte et chemins système supprimés. Rien n'est stocké.*",
        "en": "🔒 *File anonymized before analysis: IPs, ports, account IDs and system paths removed. Nothing is stored.*",
        "no": "🔒 *Filen anonymiseres før analyse: IP-er, porter, konto-ID-er og systemstier fjernes. Ingenting lagres.*",
    },
    "an.players": {"fr": "👥 Joueurs (pseudos en jeu)", "en": "👥 Players (in-game names)", "no": "👥 Spillere (spillnavn)"},
    "an.arby": {"fr": "⚖️ **Arbitration détectée**", "en": "⚖️ **Arbitration detected**", "no": "⚖️ **Arbitration oppdaget**"},
    "an.std": {"fr": "🎮 Mission standard", "en": "🎮 Standard mission", "no": "🎮 Vanlig oppdrag"},
    "an.mission": {"fr": "🗺️ Mission", "en": "🗺️ Mission", "no": "🗺️ Oppdrag"},
    "an.not_detected": {"fr": "*Non détectée*", "en": "*Not detected*", "no": "*Ikke funnet*"},
    "an.duration": {"fr": "⏱️ Durée de session", "en": "⏱️ Session length", "no": "⏱️ Øktvarighet"},
    "an.migrations": {"fr": "🔄 Migrations d'hôte", "en": "🔄 Host migrations", "no": "🔄 Vertsmigrasjoner"},
    "an.joins": {"fr": "📥 Arrivées / 📤 Départs", "en": "📥 Joins / 📤 Leaves", "no": "📥 Inn / 📤 Ut"},
    "an.warnerr": {"fr": "⚠️ Warnings / 🛑 Erreurs", "en": "⚠️ Warnings / 🛑 Errors", "no": "⚠️ Advarsler / 🛑 Feil"},
    "an.nodash": {
        "fr": "*Ce log ne contient pas d'événements de spawn. Le dashboard complet s'affiche automatiquement quand ils sont présents.*",
        "en": "*This log has no spawn events. The full dashboard appears automatically when they are present.*",
        "no": "*Denne loggen mangler spawn-hendelser. Det fulle dashbordet vises automatisk når de finnes.*",
    },
    "an.nodash.title": {"fr": "ℹ️ Dashboard détaillé indisponible", "en": "ℹ️ Detailed dashboard unavailable", "no": "ℹ️ Detaljert dashbord utilgjengelig"},
    "an.privacy.title": {"fr": "🔒 Confidentialité", "en": "🔒 Privacy", "no": "🔒 Personvern"},
    "an.lines": {"fr": "{n} lignes analysées", "en": "{n} lines parsed", "no": "{n} linjer analysert"},
    # ----- Maps -----
    "map.saved": {"fr": "✅ Map enregistrée : {name}", "en": "✅ Map saved: {name}", "no": "✅ Kart lagret: {name}"},
    "map.mode": {"fr": "🎯 Mode", "en": "🎯 Mode", "no": "🎯 Modus"},
    "map.compo": {"fr": "👥 Compo", "en": "👥 Squad comp", "no": "👥 Lagoppsett"},
    "map.compo.reco": {"fr": "👥 Compo recommandée", "en": "👥 Recommended comp", "no": "👥 Anbefalt oppsett"},
    "map.notes": {"fr": "📝 Notes", "en": "📝 Notes", "no": "📝 Notater"},
    "map.removed": {"fr": "🗑️ Map supprimée : {name}", "en": "🗑️ Map removed: {name}", "no": "🗑️ Kart fjernet: {name}"},
    "map.notfound": {"fr": "Map **{name}** introuvable.", "en": "Map **{name}** not found.", "no": "Fant ikke kartet **{name}**."},
    "map.unset": {
        "fr": "Map **{name}** non configurée. Voir `/maps` pour la liste.",
        "en": "Map **{name}** is not configured. See `/maps` for the list.",
        "no": "Kartet **{name}** er ikke satt opp. Se `/maps` for listen.",
    },
    "map.none.title": {"fr": "🗺️ Aucune map configurée", "en": "🗺️ No maps configured", "no": "🗺️ Ingen kart satt opp"},
    "map.none.desc": {
        "fr": "Un admin peut en ajouter avec `/map-add`.",
        "en": "An admin can add one with `/map-add`.",
        "no": "En admin kan legge til med `/map-add`.",
    },
    "map.list.title": {"fr": "🗺️ Maps configurées", "en": "🗺️ Configured maps", "no": "🗺️ Oppsatte kart"},
    "map.list.desc": {
        "fr": "Tapez `/map <nom>` pour le détail d'une map.",
        "en": "Type `/map <name>` for a map's details.",
        "no": "Skriv `/map <navn>` for detaljer om et kart.",
    },
    "map.count": {"fr": "{n} map(s)", "en": "{n} map(s)", "no": "{n} kart"},
    "map.compo.label": {"fr": "**Compo :**", "en": "**Comp:**", "no": "**Oppsett:**"},
    # ----- Builds -----
    "b.frame": {"fr": "🤖 Warframe", "en": "🤖 Warframe", "no": "🤖 Warframe"},
    "b.cat": {"fr": "🏷️ Catégorie", "en": "🏷️ Category", "no": "🏷️ Kategori"},
    "b.mods": {"fr": "🧩 Mods", "en": "🧩 Mods", "no": "🧩 Mods"},
    "b.arcanes": {"fr": "✨ Arcanes", "en": "✨ Arcanes", "no": "✨ Arcanes"},
    "b.shards": {"fr": "💎 Éclats d'Archonte", "en": "💎 Archon Shards", "no": "💎 Archon Shards"},
    "b.footer": {"fr": "Build {i}/{n}", "en": "Build {i}/{n}", "no": "Build {i}/{n}"},
    "b.prev": {"fr": "◀ Précédent", "en": "◀ Previous", "no": "◀ Forrige"},
    "b.next": {"fr": "Suivant ▶", "en": "Next ▶", "no": "Neste ▶"},
    "b.nocat": {
        "fr": "Aucun build trouvé pour la catégorie « {cat} ».",
        "en": "No build found for category “{cat}”.",
        "no": "Fant ingen build i kategorien «{cat}».",
    },
    "b.added": {"fr": "✅ Build ajouté : {name} ({frame})", "en": "✅ Build added: {name} ({frame})", "no": "✅ Build lagt til: {name} ({frame})"},
    "b.added.hint": {
        "fr": "Ajoutez une capture avec `/build-image` si vous voulez.",
        "en": "Attach a screenshot with `/build-image` if you like.",
        "no": "Legg gjerne ved et skjermbilde med `/build-image`.",
    },
    "b.removed": {"fr": "🗑️ Build supprimé : {name}", "en": "🗑️ Build removed: {name}", "no": "🗑️ Build fjernet: {name}"},
    "b.notfound": {
        "fr": "Build **{name}** introuvable (les builds par défaut ne peuvent pas être supprimés).",
        "en": "Build **{name}** not found (default builds cannot be removed).",
        "no": "Fant ikke builden **{name}** (standardbuilds kan ikke fjernes).",
    },
    "b.img.notfound": {"fr": "Build **{name}** introuvable.", "en": "Build **{name}** not found.", "no": "Fant ikke builden **{name}**."},
    "b.img.badfmt": {
        "fr": "Format non géré : envoyez du png, jpg, webp ou gif.",
        "en": "Unsupported format: send png, jpg, webp or gif.",
        "no": "Formatet støttes ikke: send png, jpg, webp eller gif.",
    },
    "b.img.toobig": {"fr": "Image trop lourde (max 8 Mo).", "en": "Image too large (max 8 MB).", "no": "Bildet er for stort (maks 8 MB)."},
    "b.img.saved": {"fr": "✅ Image enregistrée pour {name}", "en": "✅ Image saved for {name}", "no": "✅ Bilde lagret for {name}"},
    "b.img.saved.desc": {
        "fr": "Elle s'affichera désormais dans `/builds`.",
        "en": "It will now appear in `/builds`.",
        "no": "Det vises nå i `/builds`.",
    },
    # ----- Tracker -----
    "tr.title": {"fr": "⚖️ Suivi des Arbitrations", "en": "⚖️ Arbitration Tracker", "no": "⚖️ Arbitration-oversikt"},
    "tr.desc": {
        "fr": "Notation communautaire de **F** à **S** (ajustable avec `/tier-set`).",
        "en": "Community rating from **F** to **S** (adjustable with `/tier-set`).",
        "no": "Fellesskapsvurdering fra **F** til **S** (justerbar med `/tier-set`).",
    },
    "tr.refresh": {"fr": "Actualisé toutes les {n} min", "en": "Refreshes every {n} min", "no": "Oppdateres hvert {n}. min"},
    "tr.current": {"fr": "🔥 En cours", "en": "🔥 Current", "no": "🔥 Pågår"},
    "tr.upcoming": {"fr": "🗓️ À venir", "en": "🗓️ Upcoming", "no": "🗓️ Kommer"},
    "tr.ends": {"fr": "⏳ Se termine {when}", "en": "⏳ Ends {when}", "no": "⏳ Slutter {when}"},
    "tr.nodata": {
        "fr": "*Donnée momentanément indisponible (sources muettes ou non résolues). Réessai automatique dans quelques minutes — un admin peut lancer `/sources` pour diagnostiquer.*",
        "en": "*Data temporarily unavailable (sources down or unresolved). Automatic retry in a few minutes — an admin can run `/sources` to diagnose.*",
        "no": "*Data midlertidig utilgjengelig (kildene svarer ikke). Prøver igjen om noen minutter — en admin kan kjøre `/sources` for å feilsøke.*",
    },
    "tr.nopred": {"fr": "*Prédictions indisponibles pour le moment.*", "en": "*Predictions unavailable right now.*", "no": "*Prognoser er utilgjengelige akkurat nå.*"},
    "tr.installed.title": {"fr": "✅ Tracker installé", "en": "✅ Tracker installed", "no": "✅ Oversikt installert"},
    "tr.installed.desc": {
        "fr": "Le message sera actualisé toutes les {n} minutes. Épinglez-le pour le retrouver facilement !",
        "en": "The message will refresh every {n} minutes. Pin it to find it easily!",
        "no": "Meldingen oppdateres hvert {n}. minutt. Fest den så den er lett å finne!",
    },
    "tr.stopped": {"fr": "🗑️ Tracker arrêté", "en": "🗑️ Tracker stopped", "no": "🗑️ Oversikt stoppet"},
    "tr.noactive": {"fr": "Aucun tracker actif sur ce serveur.", "en": "No active tracker on this server.", "no": "Ingen aktiv oversikt på denne serveren."},
    "tr.tierset": {"fr": "✅ {emoji} {node} noté {tier}", "en": "✅ {emoji} {node} rated {tier}", "no": "✅ {emoji} {node} vurdert til {tier}"},
    "tr.tierset.desc": {
        "fr": "La note sera appliquée à la prochaine actualisation du tracker.",
        "en": "The rating applies at the next tracker refresh.",
        "no": "Vurderingen gjelder fra neste oppdatering.",
    },
    # ----- /help -----
    "h.title": {"fr": "📖 Commandes d'ArbyFhaps", "en": "📖 ArbyFhaps commands", "no": "📖 ArbyFhaps-kommandoer"},
    "h.desc": {
        "fr": "Le bot Arbitration de votre serveur : analyse de runs, maps, builds et suivi des arbitrations.",
        "en": "Your server's Arbitration bot: run analysis, maps, builds and arbitration tracking.",
        "no": "Serverens Arbitration-bot: rundeanalyse, kart, builds og arbitration-oversikt.",
    },
    "h.analyse.name": {"fr": "📊 Analyse de run", "en": "📊 Run analysis", "no": "📊 Rundeanalyse"},
    "h.analyse.value": {
        "fr": "`/analyse` — Analysez votre fichier `EE.log` (`%LOCALAPPDATA%\\Warframe\\EE.log`).\n🔒 IPs, IDs et données perso supprimés automatiquement, rien n'est stocké.",
        "en": "`/analyse` — Analyze your `EE.log` file (`%LOCALAPPDATA%\\Warframe\\EE.log`).\n🔒 IPs, IDs and personal data are stripped automatically, nothing is stored.",
        "no": "`/analyse` — Analyser `EE.log`-filen din (`%LOCALAPPDATA%\\Warframe\\EE.log`).\n🔒 IP-er, ID-er og persondata fjernes automatisk, ingenting lagres.",
    },
    "h.maps.name": {"fr": "🗺️ Maps & compos", "en": "🗺️ Maps & comps", "no": "🗺️ Kart & oppsett"},
    "h.maps.value": {
        "fr": "`/map <nom>` — Compo recommandée pour une map\n`/maps` — Liste des maps configurées\n`/map-add` 🔧 — Ajouter/mettre à jour une map\n`/map-remove` 🔧 — Supprimer une map",
        "en": "`/map <name>` — Recommended comp for a map\n`/maps` — List configured maps\n`/map-add` 🔧 — Add/update a map\n`/map-remove` 🔧 — Remove a map",
        "no": "`/map <navn>` — Anbefalt oppsett for et kart\n`/maps` — Liste over kart\n`/map-add` 🔧 — Legg til/oppdater kart\n`/map-remove` 🔧 — Fjern kart",
    },
    "h.builds.name": {"fr": "⚖️ Builds Arbitration", "en": "⚖️ Arbitration builds", "no": "⚖️ Arbitration-builds"},
    "h.builds.value": {
        "fr": "`/builds [categorie]` — Guide des builds (navigation ◀ ▶, avec captures)\n`/build-add` 🔧 — Ajouter un build personnalisé\n`/build-image` 🔧 — Attacher une capture d'écran à un build\n`/build-remove` 🔧 — Supprimer un build personnalisé",
        "en": "`/builds [category]` — Build guide (◀ ▶ navigation, with screenshots)\n`/build-add` 🔧 — Add a custom build\n`/build-image` 🔧 — Attach a screenshot to a build\n`/build-remove` 🔧 — Remove a custom build",
        "no": "`/builds [kategori]` — Build-guide (◀ ▶-navigering, med skjermbilder)\n`/build-add` 🔧 — Legg til egen build\n`/build-image` 🔧 — Legg ved skjermbilde\n`/build-remove` 🔧 — Fjern egen build",
    },
    "h.tracker.name": {"fr": "⏰ Suivi des arbitrations", "en": "⏰ Arbitration tracking", "no": "⏰ Arbitration-oversikt"},
    "h.tracker.value": {
        "fr": "`/arbitration` — Arbitration en cours + prochaines, notées de F à S\n`/tracker-start` 🔧 — Message auto-actualisé dans le salon\n`/tracker-stop` 🔧 — Arrête le message auto-actualisé\n`/tier-set` 🔧 — Ajuste la note d'un nœud pour ce serveur",
        "en": "`/arbitration` — Current + upcoming arbitrations, rated F to S\n`/tracker-start` 🔧 — Auto-refreshing message in this channel\n`/tracker-stop` 🔧 — Stop the auto-refreshing message\n`/tier-set` 🔧 — Adjust a node's rating for this server",
        "no": "`/arbitration` — Pågående + kommende arbitrations, vurdert F til S\n`/tracker-start` 🔧 — Selvoppdaterende melding i kanalen\n`/tracker-stop` 🔧 — Stopp meldingen\n`/tier-set` 🔧 — Juster et kartpunkts vurdering",
    },
    "h.misc.name": {"fr": "ℹ️ Divers", "en": "ℹ️ Misc", "no": "ℹ️ Diverse"},
    "h.misc.value": {
        "fr": "`/language` — Choisir votre langue (rien que pour vous)\n`/help` — Cette aide\n🔧 = réservé aux admins (permission « Gérer le serveur »)",
        "en": "`/language` — Pick your language (just for you)\n`/help` — This help\n🔧 = admin only (“Manage Server” permission)",
        "no": "`/language` — Velg språket ditt (bare for deg)\n`/help` — Denne hjelpen\n🔧 = kun admin («Administrer server»)",
    },
}
