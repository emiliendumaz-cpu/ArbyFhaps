# ArbyFhaps ⚖️

Bot Discord dédié à l'**Arbitration** sur Warframe : analyse de runs via le fichier `EE.log`, configuration des maps et compos recommandées, et guide des builds.

## Fonctionnalités

### 📊 `/analyse` — Analyse d'un run
Uploadez votre fichier `EE.log` (sur Windows : `%LOCALAPPDATA%\Warframe\EE.log`) et le bot génère un **dashboard image** (style sombre/or) :

- Tuiles de stats : ennemis apparus, kills par drone, intervalle drone moyen, drones tués, Vitus par minute, durée totale
- Table de probabilité de Vitus (pire cas → roll divin) avec le percentile de votre run
- Saturation ennemis : % du temps passé à chaque nombre d'ennemis vivants
- Drones et spawns par intervalle (graphiques avec moyenne)

Si le log ne contient pas les événements de spawn, le bot renvoie un résumé simple en embed : mission, durée, joueurs (pseudos en jeu uniquement), migrations d'hôte, arrivées/départs, warnings/erreurs moteur.

**🔒 Confidentialité — le log est trié avant analyse :** les adresses IP (v4/v6), ports, IDs de compte/GUID, adresses MAC, le login du compte et les chemins système contenant le nom d'utilisateur Windows sont **supprimés du texte avant toute analyse**. Le fichier n'est **jamais stocké** : il est lu en mémoire, analysé, puis oublié. Il est donc impossible de récupérer l'IP d'un joueur via le bot.

### 🗺️ Maps & compos
- `/map-add` *(admin)* — enregistre une map avec son mode, sa compo recommandée et des notes
- `/map <nom>` — affiche la compo recommandée pour une map (avec autocomplétion)
- `/maps` — liste toutes les maps configurées
- `/map-remove` *(admin)* — supprime une map

Chaque serveur Discord a sa propre configuration.

### ⚖️ `/builds` — Guide des builds Arbitration
- `/builds [categorie]` — affiche les builds spécial Arbitration (navigation par boutons). Des builds par défaut sont fournis (Saryn, Octavia, Wisp, Khora, Nekros, Frost + conseils généraux).
- `/build-add` *(admin)* — ajoute un build personnalisé propre au serveur
- `/build-remove` *(admin)* — supprime un build personnalisé

### ⏰ Suivi des arbitrations (message auto-actualisé)
- `/tracker-start` *(admin)* — installe dans le salon un message que le bot **édite automatiquement toutes les 5 minutes** : arbitration en cours (nœud, mode, ennemi, compte à rebours) et prochaines arbitrations quand la source de prédictions répond
- `/arbitration` — la même chose en une fois, sans message permanent
- `/tracker-stop` *(admin)* — arrête et supprime le message
- `/tier-set` *(admin)* — ajuste la note d'un nœud pour ce serveur

Chaque arbitration est **notée de F à S**. Priorité : note fixée par le serveur (`/tier-set`, par nom de nœud ou par identifiant `SolNodeXXX`) > note officielle de browse.wf > repli par mode de mission.

Source : le bot consomme les mêmes fichiers publics que la page [browse.wf/arbys](https://browse.wf/arbys) — le planning pré-généré `arbys.txt` (heure par heure, en cours **et** à venir), `ExportRegions.json` pour les nœuds, le dictionnaire FR pour les noms, et `arbyTiers.js` pour les notes officielles (merci aux Arbitration Goons), avec une copie locale de secours dans `data/arby_tiers.json`.

### 📖 `/help`
Affiche la liste de toutes les commandes du bot (réponse visible par vous seul).

## Installation

1. Créez une application sur https://discord.com/developers/applications, ajoutez un **Bot** et copiez son token. Aucun intent privilégié n'est nécessaire.
2. Invitez le bot avec le scope `applications.commands` + `bot` (permissions : Envoyer des messages, Intégrer des liens, Joindre des fichiers).
3. Installez et lancez :

**Windows — méthode simple :** double-cliquez sur `start.bat`. Il crée l'environnement, installe les dépendances et lance le bot automatiquement (il faut d'abord avoir créé le fichier `.env`, voir ci-dessous).

**Méthode manuelle :**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # puis renseignez DISCORD_TOKEN
python bot.py
```

En développement, renseignez `GUILD_ID` dans `.env` pour que les commandes slash apparaissent immédiatement sur votre serveur (la synchronisation globale peut prendre jusqu'à une heure).

## Structure du projet

```
bot.py               # Point d'entrée, chargement des cogs, sync des commandes
cogs/analyze.py      # /analyse — analyse EE.log
cogs/maps.py         # /map-add /map-remove /maps /map
cogs/builds.py       # /builds /build-add /build-remove
utils/eelog.py       # Parseur EE.log + anonymisation (IP, IDs, MAC, chemins…)
utils/storage.py     # Stockage JSON par serveur (data/guilds/, non versionné)
data/builds.json     # Builds Arbitration par défaut
```
