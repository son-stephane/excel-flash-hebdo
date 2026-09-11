# Flash hebdomadaire

Automatisation de bout en bout du flash hebdomadaire : extraction du portail,
historisation figée, contrôles qualité, classeur Excel, graphiques et mail.

```
Portail  ──► 00_raw ──► 10_snapshots ──► contrôles ──► 30_mart ──► Excel / PNG ──► mail
 Playwright   archive     Parquet figé     bloquants     SQL        TCD, graphes   brouillon
              horodatée   (1 par semaine)                                          Outlook
```

## Pourquoi des fichiers Parquet plutôt qu'un onglet Excel

L'export du portail contient **tout l'historique à chaque extraction**, soit
~110 000 lignes par semaine. Empilées, cela fait ~5,7 millions de lignes par
an : une feuille Excel est saturée (limite 1 048 576 lignes) au bout de neuf
semaines, là où le même volume tient dans ~200 Mo de Parquet.

Un fichier Parquet est écrit une fois et n'est plus jamais modifié. C'est ce
qui rend le stockage compatible avec une synchro SharePoint/OneDrive : des
fichiers qui s'ajoutent, jamais un gros fichier réécrit en permanence — donc
pas de « copie en conflit ». DuckDB lit directement ces fichiers en SQL, sans
serveur à installer.

**SharePoint et Parquet ne s'opposent pas** : SharePoint est *l'emplacement*,
Parquet est *le format*. Pointer `chemins.racine_donnees` vers le dossier
synchronisé une fois le projet en production.

## Démarrage

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows : .venv\Scripts\pip install -e ".[windows,dev]"
.venv/bin/python -m flash init
```

Variante par `requirements.txt`, pour les environnements où l'installation
passe par un miroir interne ou une revue IT. Les deux commandes sont
nécessaires : la première installe les dépendances, la seconde le paquet
`flash` lui-même — sans elle, `python -m flash` ne trouvera rien, le projet
utilisant une disposition `src/`.

```bash
pip install -r requirements-windows.txt   # ou requirements.txt hors Windows
pip install -e . --no-deps
```

Pour essayer sans accès au portail, un générateur produit des exports factices
qui reproduisent les deux comportements qui comptent — historique complet
re-téléchargé, et corrections rétroactives d'une semaine à l'autre :

```bash
python scripts/make_sample_data.py --semaines 2026-W35 2026-W36 2026-W37
python -m flash run --semaine 2026-W35 --sans-extraction --sans-mail --sans-excel
python -m flash run --semaine 2026-W36 --sans-extraction --sans-mail --sans-excel
python -m flash run --semaine 2026-W37 --sans-extraction --sans-excel
```

## Commandes

| Commande | Rôle |
|---|---|
| `flash run` | chaîne complète sur la semaine courante |
| `flash etat` | quels fichiers sont disponibles pour la semaine |
| `flash extraire` | télécharger depuis le portail |
| `flash ingerer` | brut → snapshot Parquet figé |
| `flash controler` | contrôles qualité seuls (code retour 1 si bloquant) |
| `flash mart` | reconstruire la table agrégée |
| `flash graphiques` | graphiques Python |
| `flash classeur` | classeur Excel : injection, TCD, export PNG |
| `flash mail` | préparer le mail |
| `flash detail --ou "..."` | **remonter aux lignes sources d'un chiffre** |
| `flash sql "..."` | requête libre sur les snapshots |
| `flash semaines` | historique disponible |

Options utiles de `run` : `--semaine 2026-W37`, `--sans-extraction` (repartir
d'un fichier déposé à la main), `--sans-mail`, `--sans-excel`, `--forcer`
(publier malgré un contrôle bloquant).

## Interface pour l'utilisateur final

La personne qui exécute le flash chaque semaine n'a **rien à lancer** :
l'interface tourne en tâche de fond et elle ouvre un favori.

```bash
streamlit run app/streamlit_app.py --server.port 8501
```

`scripts/installer_taches.ps1` installe la tâche planifiée Windows qui démarre
cette interface à l'ouverture de session — voir `docs/mise-en-production.md`.

## Structure

```
config/
  settings.toml              réglages versionnés
  settings.local.toml        surcharges du poste (non versionné)
  schemas/*.toml             structure, filtrage et contrôles de chaque rapport
src/flash/
  extract/portail.py        Playwright : login, exécution, téléchargement
  extract/inbox.py           mode dégradé : dépôt manuel
  ingest/snapshots.py        brut → Parquet figé, typage, filtrage
  quality/checks.py          contrôles bloquants
  quality/diff.py            comparaison N / N-1, corrections rétroactives
  transform/sql/*.sql        LA logique métier, versionnée
  publish/excel.py           injection, refresh TCD, export PNG
  publish/charts.py          graphiques matplotlib (moteur de secours)
  publish/mail.py            brouillon Outlook, repli .eml
  pipeline.py                orchestration — appelée par CLI, UI et planificateur
  drill.py                   remontée aux lignes sources
app/streamlit_app.py         façade utilisateur
scripts/                     données de test, template Excel, tâches planifiées
```

## Adapter le projet à vos vrais rapports

1. **Décrire les rapports** dans `config/schemas/` : un fichier par requête
   du portail. Les noms `source` doivent correspondre exactement aux en-têtes du
   fichier produit. Renseigner la clef métier, la colonne de date, le filtrage
   et les seuils de contrôle.
2. **Relever les sélecteurs du portail** avec `playwright codegen <url>` et les
   reporter dans `SELECTEURS`, en haut de `src/flash/extract/portail.py`.
3. **Écrire la logique métier** dans `src/flash/transform/sql/mart_flash_hebdo.sql`.
   C'est la seule définition des chiffres publiés — ne jamais agréger ailleurs,
   sinon la remontée aux lignes sources cesse d'être fiable.
4. **Aligner le template Excel** (`python scripts/make_template.py`, puis
   ajouter les TCD dans Excel avec le tableau structuré pour source).

## Tests

```bash
.venv/bin/python -m pytest
```

## Documentation

- `docs/mise-en-production.md` — déploiement Windows, planification, SharePoint
- `docs/demarrage.md` — procédure de mise en route pas à pas
- `docs/enquete.md` — que faire quand un graphique paraît faux
