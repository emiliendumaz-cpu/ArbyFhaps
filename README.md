# ArbyFhaps 🤖

Bot Discord dédié aux **arbitrations Warframe** : analyse de runs via `EE.log`,
compos recommandées par map, et guide des builds.

## ✨ Commandes

| Commande | Description |
|---|---|
| `/analyse <fichier>` | Analyse une run à partir de ton `EE.log` (mission, durée, escouade, migrations d'hôte…). **Toutes les données sensibles sont supprimées avant analyse.** |
| `/builds` | Guide des builds spécial arbitration, avec menu par catégorie (Warframes, armes, compagnons, règles d'or). |
| `/build definir` | (Admin) Ajoute ou modifie un build : catégorie, nom, description, mods, conseils. Même nom = mise à jour. |
| `/build supprimer` | (Admin) Supprime un build (une catégorie vidée disparaît du menu). |
| `/build categories` | (Admin) Liste les catégories et le nombre de builds. |
| `/map liste` | Liste les maps configurées. |
| `/map info <nom>` | Affiche la compo recommandée pour une map. |
| `/map definir` | (Admin) Ajoute/modifie une map, son type et sa compo. |
| `/map supprimer` | (Admin) Supprime une map. |
| `/langue` | Choisis ta langue (Français / English / Auto). Chaque joueur a la sienne ; en mode Auto, le bot suit la langue du client Discord. |
| `/arby actuelle` | Affiche l'arbitration en cours (map, type, faction, temps restant, compo recommandée si la map est configurée). |
| `/arby suivre` | (Admin) Poste un message dynamique dans le salon, **actualisé automatiquement à chaque rotation d'arbitration** — la map méta est marquée ⭐ avec sa compo. |
| `/arby stop` | (Admin) Arrête le suivi dynamique sur le serveur. |

## 🔒 Confidentialité

Le fichier `EE.log` de Warframe contient des données réseau (adresses IP des
autres joueurs, identifiants de compte, chemins de ta machine). Le bot est
conçu pour qu'il soit **impossible** d'y accéder :

- Le log est **anonymisé en mémoire avant toute analyse** (`utils/eelog.py`) :
  IPv4/IPv6, ports, GUID, identifiants de compte, tickets de session, lignes
  réseau NAT/relais, chemins Windows avec nom d'utilisateur — tout est supprimé.
- Le fichier **n'est jamais écrit sur le disque** et n'est pas conservé après
  la réponse.
- Le bot n'affiche que : nœud de mission, type, durée, pseudos de l'escouade,
  Warframes détectées, migrations d'hôte, remarques.
- Aucun intent privilégié Discord : le bot ne lit pas les messages du serveur.

## 🚀 Installation

1. Créez une application sur https://discord.com/developers/applications,
   ajoutez un **Bot**, copiez son token.
2. Invitez le bot sur votre serveur avec le scope `applications.commands` + `bot`
   (permissions : Envoyer des messages, Intégrer des liens).
3. Puis :

```bash
git clone <ce-repo>
cd ArbyFhaps
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # et remplir DISCORD_TOKEN (+ GUILD_ID pour une synchro instantanée en dev)
python bot.py
```

> Sans `GUILD_ID`, les commandes sont synchronisées globalement — Discord peut
> mettre jusqu'à une heure à les afficher.

## 🗂️ Où trouver son EE.log ?

Windows : `%LOCALAPPDATA%\Warframe\EE.log`
(collez ce chemin dans la barre d'adresse de l'explorateur).

⚠️ Le fichier est réinitialisé au lancement du jeu : uploadez-le **après votre
run, avant de relancer Warframe**. Astuce : relancer le jeu juste avant la run
donne un log propre et léger.

## 🛠️ Personnalisation

- **Maps & compos** : via `/map definir` en jeu de commandes, ou en éditant
  `data/maps.json` (le bot relit le fichier à chaque commande).
- **Builds** : via `/build definir` et `/build supprimer` directement sur
  Discord (réservé aux admins), ou en éditant `data/builds.json`. Chaque
  catégorie est une liste d'entrées `{nom, description, mods, conseils}` —
  les catégories apparaissent automatiquement dans le menu de `/builds`, et
  une nouvelle catégorie se crée simplement en la nommant dans `/build definir`.

## 📁 Structure

```
bot.py              # point d'entrée
cogs/analyse.py     # /analyse — analyse EE.log anonymisée
cogs/maps.py        # /map — maps & compos
cogs/builds.py      # /builds — guide des builds + /build (gestion)
cogs/langue.py      # /langue — langue par joueur
cogs/arby.py        # /arby — arbitration en cours + message dynamique
utils/eelog.py      # anonymisation + parsing du EE.log
utils/i18n.py       # traductions FR/EN + préférences de langue
utils/storage.py    # lecture/écriture JSON atomique
data/maps.json      # maps configurées (modifiable)
data/builds.json    # builds du guide (modifiable)
data/langues.json   # préférences de langue (créé au premier /langue, non versionné)
```

## 🌍 Langues

L'interface du bot (réponses, embeds, erreurs) existe en **français** et en
**anglais**. Chaque joueur choisit avec `/langue` ; sans choix, le bot suit la
langue du client Discord du joueur (français par défaut pour les autres
langues). Le contenu éditable (descriptions des builds, notes des maps) reste
dans la langue où vous l'écrivez. Pour ajouter une langue : compléter chaque
entrée de `utils/i18n.py` et la liste `LANGS`.

## 🎯 Suivi dynamique de l'arbitration

`/arby suivre` poste un embed « Arbitration en cours » qui se met à jour tout
seul à chaque rotation du jeu (vérification toutes les 2 minutes via l'API
communautaire [warframestat.us](https://api.warframestat.us/pc/arbitration)).
Le compte à rebours utilise un timestamp Discord : il défile en continu sans
édition du message. Si la map en cours fait partie de vos maps configurées
(`/map definir`), l'embed la marque ⭐ et affiche la compo recommandée.
Un suivi par serveur ; il survit aux redémarrages du bot (`data/arby.json`),
et supprimer le message à la main arrête le suivi proprement.
La machine qui héberge le bot doit pouvoir joindre `api.warframestat.us` en HTTPS.

## ⚠️ Limites connues

Le format d'`EE.log` n'est pas documenté officiellement et évolue avec les
mises à jour de Warframe : le parseur est « best-effort » — il indique
clairement ce qu'il n'a pas pu détecter plutôt que d'inventer des valeurs.
