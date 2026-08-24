# ArbyFhaps 🤖

Bot Discord dédié aux **arbitrations Warframe** : analyse de runs via `EE.log`,
compos recommandées par map, et guide des builds.

## ✨ Commandes

| Commande | Description |
|---|---|
| `/analyse <fichier>` | Analyse une run à partir de ton `EE.log` (mission, durée, escouade, migrations d'hôte…). **Toutes les données sensibles sont supprimées avant analyse.** |
| `/builds` | Guide des builds spécial arbitration, avec menu par catégorie (Warframes, armes, compagnons, règles d'or). |
| `/map liste` | Liste les maps configurées. |
| `/map info <nom>` | Affiche la compo recommandée pour une map. |
| `/map definir` | (Admin) Ajoute/modifie une map, son type et sa compo. |
| `/map supprimer` | (Admin) Supprime une map. |

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
- **Builds** : éditez `data/builds.json`. Chaque catégorie est une liste
  d'entrées `{nom, description, mods, conseils}` — les catégories apparaissent
  automatiquement dans le menu de `/builds`.

## 📁 Structure

```
bot.py              # point d'entrée
cogs/analyse.py     # /analyse — analyse EE.log anonymisée
cogs/maps.py        # /map — maps & compos
cogs/builds.py      # /builds — guide des builds
utils/eelog.py      # anonymisation + parsing du EE.log
utils/storage.py    # lecture/écriture JSON atomique
data/maps.json      # maps configurées (modifiable)
data/builds.json    # builds du guide (modifiable)
```

## ⚠️ Limites connues

Le format d'`EE.log` n'est pas documenté officiellement et évolue avec les
mises à jour de Warframe : le parseur est « best-effort » — il indique
clairement ce qu'il n'a pas pu détecter plutôt que d'inventer des valeurs.
