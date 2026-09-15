# Rapports hebdomadaires par DR

Automatisation d'un rapport hebdomadaire : filtrage d'une extraction Excel,
comptage par DR, confrontation aux objectifs, et production d'un rapport HTML
et d'un classeur Excel.

```
extraction.xlsx ─┐
                 ├─► filtre date + segment ─► volumes par DR ─► R/O, écart
objectifs.xlsx ──┘                                    │
                                                      ├─► rapport.html          page autonome
                                                      ├─► rapport.xlsx          nouveau classeur
                                                      └─► classeur existant     onglets remplis
```

Les trois restitutions vivent en parallèle : le classeur historique continue
d'être alimenté pendant que les deux nouvelles formes s'installent.

Le téléchargement des fichiers depuis le site n'est pas couvert : déposer les
classeurs dans `data\entrees\` et lancer la commande.

## Démarrage

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Essayer sans les vrais fichiers :

```powershell
python scripts\generer_exemple.py
rapport run
```

Les sorties arrivent dans `data\sorties\<semaine>\`.

## Commandes

| Commande | Rôle |
|---|---|
| `rapport run` | tous les rapports, semaine courante |
| `rapport run --semaine 2026-W37` | une semaine précise |
| `rapport run --rapport activite` | un seul rapport |
| `rapport liste` | rapports configurés |
| `rapport verifier` | les fichiers attendus sont-ils présents ? |

## Les trois sorties

Chaque exécution écrit dans `data\sorties\<semaine>\` :

| Fichier | Usage |
|---|---|
| `<rapport>_<semaine>.html` | page autonome, sans ressource externe : lisible hors ligne, envoyable par mail |
| `<rapport>_<semaine>.xlsx` | nouveau classeur, tableau formaté et graphique Excel natif |
| `rapport_existant_<semaine>.xlsx` | copie du classeur historique, ses trois onglets remplis |
| `<rapport>_<semaine>.png` | le graphique seul |

Le classeur historique part d'un modèle placé dans `templates\classeur\`, qui
n'est jamais modifié. Voir
[docs/ancienne-version-excel.md](docs/ancienne-version-excel.md).

## Ce que produit le rapport

Une ligne par DR, puis deux lignes de total — toutes DR, et hors la DR
désignée dans la configuration.

| Colonne | Signification |
|---|---|
| Réalisé semaine | lignes dont la date tombe dans les 7 jours |
| Réalisé cumul | lignes du 1er janvier au dimanche de la semaine |
| Objectif début année | lu dans le fichier des objectifs |
| **R/O** | **réalisé cumul ÷ objectif début année** |
| Écart | réalisé cumul − objectif début année |
| Objectif annuel | lu dans le fichier des objectifs |
| % objectif annuel | position du cumul dans l'année entière |

Deux règles qui évitent les malentendus :

- **Le R/O porte sur le cumul, pas sur la semaine.** Comparer sept jours à un
  objectif début d'année n'aurait pas de sens. La colonne « Réalisé semaine »
  suit l'activité mais n'entre dans aucun ratio.
- **Le R/O des totaux est recalculé à partir des sommes**, jamais obtenu en
  moyennant les R/O des DR : une moyenne de ratios de poids différents ne veut
  rien dire.

## Configuration

Tout est déclaratif dans `config\rapports.toml` : motifs de fichiers, noms de
colonnes, segments à conserver, DR à sortir du total. Ajouter un rapport, c'est
ajouter un bloc `[[rapports]]` — sans écrire de code.

```toml
[rapports.colonnes]
date = "Date CAV"      # à gauche le rôle attendu, à droite l'en-tête du fichier
segment = "Segment"
dr = "Code DR"
```

Si un en-tête ne correspond pas, l'exécution s'arrête et liste les colonnes
réellement présentes dans le fichier.

## Structure

```
config/rapports.toml          toute la configuration
src/rapports/
  config.py                   lecture et validation de la configuration
  semaines.py                 semaines ISO, bornes, début d'année
  sources.py                  lecture des classeurs, contrôle des colonnes
  calculs.py                  filtres, volumes par DR, R/O, totaux
  sorties/graphique.py        graphique R/O (PNG)
  sorties/excel.py            classeur avec graphique Excel natif
  sorties/html.py             page autonome
  pipeline.py                 enchaînement complet
  cli.py                      ligne de commande
  sorties/classeur_existant.py  remplissage du classeur historique
templates/rapport.html.j2     gabarit du rapport HTML
templates/classeur/           le classeur historique, modèle jamais modifié
scripts/generer_exemple.py    fichiers d'exemple
tests/                        43 tests, dont les règles de calcul
```

## Tests

```powershell
pytest
```

## Documentation

- [docs/execution.md](docs/execution.md) — installation, exécution hebdomadaire, dépannage
- [docs/ajouter-un-rapport.md](docs/ajouter-un-rapport.md) — ajouter un rapport, et ce qui demande du code
- [docs/ancienne-version-excel.md](docs/ancienne-version-excel.md) — faire vivre le classeur historique (sans notion technique)
