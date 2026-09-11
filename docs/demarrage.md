# Mode opératoire

Procédure complète de mise en route sur le poste de travail, du transfert des
fichiers jusqu'au cycle hebdomadaire. À suivre dans l'ordre : chaque étape
suppose la précédente validée.

Les commandes sont données pour PowerShell sur Windows.

---

## Sommaire

0. [Transférer le projet et vérifier son intégrité](#0-transférer-le-projet-et-vérifier-son-intégrité)
1. [Installer l'environnement](#1-installer-lenvironnement)
2. [Valider la chaîne sur des données factices](#2-valider-la-chaîne-sur-des-données-factices)
3. [Brancher les vrais rapports](#3-brancher-les-vrais-rapports)
4. [Écrire la logique métier](#4-écrire-la-logique-métier)
5. [Le classeur Excel](#5-le-classeur-excel)
6. [Le mail](#6-le-mail)
7. [Automatiser le téléchargement](#7-automatiser-le-téléchargement)
8. [Passer la main à l'utilisateur](#8-passer-la-main-à-lutilisateur)
9. [Le cycle hebdomadaire](#9-le-cycle-hebdomadaire)
10. [Dépannage](#10-dépannage)
11. [Aide-mémoire des commandes](#11-aide-mémoire-des-commandes)

---

## 0. Transférer le projet et vérifier son intégrité

Transférer l'archive `excel-flash-hebdo.zip` **d'un seul bloc**, et l'extraire
dans un dossier **vierge** — jamais par-dessus une copie existante, sinon les
fichiers abîmés survivent au remplacement.

Avant toute installation, vérifier que rien n'a été perdu en chemin :

```powershell
python verifier_integrite.py
```

Résultat attendu :

```
54 fichier(s) conformes

Le projet est complet et intact. Installation possible.
```

Le script compare chaque fichier à son empreinte SHA-256 enregistrée dans
`MANIFESTE.txt`. En cas d'écart, il indique le fichier, la taille reçue et la
taille attendue.

> **Ne pas sauter cette étape.** Une copie partielle ne se manifeste pas tout
> de suite : elle produit, plus tard, des erreurs du type
> `module 'flash.publish.charts' has no attribute 'produire'`, dont la cause
> réelle est invisible. Et `pytest` ne la détectera pas : la suite de tests ne
> couvre pas les modules de publication.

Si le projet est suivi par git, `git status` remplit le même rôle.

---

## 1. Installer l'environnement

### Créer et activer l'environnement virtuel

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

L'invite se préfixe de `(.venv)`. À partir de là, `python`, `pip`, `pytest` et
`flash` pointent vers cet environnement.

**L'activation ne vaut que pour la fenêtre en cours** : elle est à refaire à
chaque nouvelle session PowerShell.

Si la politique d'exécution bloque le script d'activation, lever la
restriction pour la seule fenêtre courante — sans droits administrateur et
sans modification durable du poste :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Si même cela échoue (stratégie de groupe imposée au niveau machine), passer
par `cmd.exe`, où l'activation est un `.bat` :

```cmd
.venv\Scripts\activate.bat
```

### Installer les dépendances et le projet

```powershell
pip install -e ".[windows,dev]"
```

Cette commande installe **les dépendances et le projet** en une fois. Le `-e`
(*editable*) crée un lien vers `src\` plutôt qu'une copie : les modifications
de schémas ou de SQL sont prises en compte immédiatement, sans réinstaller.

Variante si l'installation doit passer par un miroir interne. Les **deux**
commandes sont nécessaires — la seconde installe le paquet `flash` lui-même,
sans quoi `flash` restera introuvable :

```powershell
pip install -r requirements-windows.txt
```

```powershell
pip install -e . --no-deps
```

### Vérifier

```powershell
pytest
```

29 tests verts. Puis :

```powershell
flash --help
```

---

## 2. Valider la chaîne sur des données factices

Avant de toucher aux vraies données, s'assurer que tout fonctionne sur ce
poste. Le générateur reproduit les deux comportements qui comptent :
historique complet re-téléchargé à chaque extraction, et corrections
rétroactives d'une semaine à l'autre.

```powershell
flash init
```

```powershell
python scripts\make_sample_data.py --semaines 2026-W36 2026-W37
```

Attendu : six lignes, environ 20 400 lignes pour les rapports A et B, 70 400
pour le C.

```powershell
flash run --semaine 2026-W36 --sans-extraction --sans-mail --sans-excel
```

Attendu : environ 20 300 lignes conservées par rapport (le filtre écarte les
« Annulé »), `21 OK, 0 alertes, 0 echecs`, un mart d'environ 9 500 lignes,
3 graphiques. Pas de comparaison possible : c'est la première semaine
historisée.

```powershell
flash run --semaine 2026-W37 --sans-extraction --sans-mail
```

Il n'y a plus de `--sans-excel` : c'est le test du pilotage d'Excel.

Attendu, en plus de la première semaine :

```
[rapport_c] 2026-W37 vs 2026-W36 : 750 ajoutees, 25 modifiees, ...
[ !! ] rapport_c  changements_retroactifs  N ligne(s) de periodes deja publiees ont change
```

L'alerte orange est le résultat **attendu** : le générateur simule des
corrections rétroactives, exactement ce que fait le portail. C'est le
mécanisme qui dira plus tard si un chiffre suspect vient de la source ou du
traitement.

### Point de décision : Excel se pilote-t-il ?

```powershell
Get-ChildItem data\90_sorties\2026-W37\graphiques | Select-Object -ExpandProperty Name
```

| Noms observés | Interprétation | Conséquence |
|---|---|---|
| `01_montant_par_mois.png`, `02_…` | graphiques **matplotlib** | Excel n'a pas pu être piloté : phase 2 directe |
| `GRAPHIQUES_…png` | graphiques **du classeur** | le pilotage fonctionne : phase 1 |

Le journal le confirme :

```powershell
Select-String -Path data\_logs\flash.log -Pattern "TCD et connexions rafraichis|Excel indisponible" | Select-Object -Last 3
```

Les deux voies fonctionnent. En phase 1, les TCD et graphiques existants
restent le livrable et les destinataires ne voient aucune rupture. En phase 2,
les graphiques sont produits en Python : plus robuste, exécutable sans Office
donc sur un serveur, mais leur apparence change et il faudra les ajuster dans
`src\flash\publish\charts.py`.

### Effacer la démonstration

```powershell
Remove-Item -Recurse -Force data\00_raw, data\10_snapshots, data\20_diff, data\30_mart, data\90_sorties
```

---

## 3. Brancher les vrais rapports

**Ne pas commencer par l'automatisation du téléchargement.** Télécharger les
rapports à la main, comme chaque semaine, et les déposer dans `data\inbox\`.

```powershell
flash etat
```

Trois `[ -- ] manquant` au premier essai : les motifs de reconnaissance ne
correspondent pas aux noms de fichiers réels. Ajuster `motif` dans le bloc
`[fichier]` de chaque `config\schemas\*.toml` jusqu'à obtenir trois `[ OK ]`.

Lire les en-têtes réels :

```powershell
Get-Content data\inbox\<ton-fichier>.csv -TotalCount 1
```

Cette ligne donne trois informations d'un coup : les noms de colonnes exacts,
le séparateur utilisé, et — si les accents apparaissent comme des caractères
parasites — que l'encodage déclaré n'est pas le bon.

```powershell
flash ingerer
```

**Le message d'erreur est le guide** : il liste les colonnes attendues *et*
celles réellement présentes. Recopier les vraies dans les blocs
`[[colonnes]]`, relancer. Deux ou trois tours suffisent généralement.

### Les quatre réglages qui coincent

Tous dans le bloc `[fichier]`, par ordre de fréquence :

| Réglage | Valeurs usuelles |
|---|---|
| `encodage` | `cp1252` pour un export Windows classique, `utf-8-sig` sinon |
| `separateur` | `;` en France, `,` pour un export anglo-saxon |
| `format_date` | `%d/%m/%Y`, `%Y-%m-%d` |
| `decimal` | `,` ou `.` |

### Les trois blocs à remplir ensuite

**`[cle]`** — la colonne qui identifie une ligne de façon stable d'une
extraction à l'autre. C'est elle qui permet de détecter les corrections
rétroactives : choisir un identifiant métier, jamais un numéro de ligne qui
bougerait d'un export à l'autre. `colonnes_comparees` liste les colonnes dont
la modification doit être signalée.

**`[filtre]`** — la règle appliquée aujourd'hui à la main dans Excel pour ne
garder que ce qui compte. **C'est l'étape la plus importante du projet** : il
s'agit de formaliser quelque chose qui se fait aujourd'hui à l'instinct.

**`[controles]`** — volumétries réelles, seuils de variation, colonnes
obligatoires, unicité, modalités attendues.

```powershell
flash controler
```

### Renommer les rapports

Pour donner des noms parlants, modifier le champ `nom =` **à l'intérieur** du
fichier TOML, pas seulement le nom du fichier. Ce nom devient celui de la vue
SQL : le répercuter dans `src\flash\transform\sql\mart_flash_hebdo.sql`.

---

## 4. Écrire la logique métier

Réécrire `src\flash\transform\sql\mart_flash_hebdo.sql` avec les vraies
colonnes et agrégations.

Vues disponibles dans ce SQL :

| Vue | Contenu |
|---|---|
| `<rapport>` | le snapshot de la semaine traitée |
| `<rapport>_historique` | tous les snapshots empilés, colonne `_semaine` |
| `marts` | tous les marts déjà produits |

Explorer sans relancer toute la chaîne :

```powershell
flash sql "SELECT * FROM rapport_a LIMIT 20"
```

```powershell
flash mart
```

> **Critère de sortie : le mart doit reproduire exactement les chiffres du
> flash de la semaine précédente.** Comparer avant d'aller plus loin. Si les
> chiffres ne coïncident pas maintenant, ils ne coïncideront jamais.

**Règle à tenir :** le mart est produit uniquement par ce SQL, jamais par des
retouches manuelles. C'est la condition pour que `flash detail` puisse
remonter aux lignes sources d'un point de graphique.

---

## 5. Le classeur Excel

```powershell
python scripts\make_template.py
```

Ouvrir `templates\flash_hebdo.xlsx` dans Excel et y ajouter les TCD :

1. Insertion → Tableau croisé dynamique ;
2. source = **le tableau structuré `tbl_donnees`** — jamais une plage figée du
   type `A1:J5000`, sinon le TCD ne suivra pas la variation du nombre de
   lignes d'une semaine à l'autre ;
3. construire les TCD et graphiques ;
4. enregistrer.

Le template est ensuite copié tel quel chaque semaine, jamais modifié en
place.

```powershell
flash classeur
```

Si Excel n'est pas pilotable, l'injection des données est quand même faite et
la chaîne bascule sur les graphiques Python : la semaine n'est pas perdue.

Pour passer délibérément aux graphiques Python, dans `settings.toml` :

```toml
[publication]
moteur_graphiques = "python"
```

---

## 6. Le mail

Créer `config\settings.local.toml` — non versionné, propre au poste :

```toml
[chemins]
racine_donnees = "C:/Users/<user>/<Entreprise>/Flash hebdo - Documents/data"

[portail]
url_connexion = "https://portail.<entreprise>.fr/login"
identifiant = "prenom.nom"

[mail]
destinataires = ["equipe@entreprise.fr"]
expediteur = "prenom.nom@entreprise.fr"

[alertes]
destinataires = ["prenom.nom@entreprise.fr"]
```

Garder `brouillon = true` les premiers mois : le coût est nul et cela évite
d'envoyer un flash faux à toute une liste de diffusion.

```powershell
flash mail
```

Si un contrôle bloquant échoue, **rien n'est diffusé** et une alerte part vers
`alertes.destinataires`.

### Le dossier SharePoint

`racine_donnees` doit pointer vers un dossier **synchronisé localement** par
le client OneDrive, pas vers une URL `https://…sharepoint.com/…`.

Le stockage est conçu pour cette synchro : les fichiers Parquet sont écrits
une fois et jamais réécrits. Ne jamais y placer un fichier de base unique
réécrit à chaque exécution — c'est la recette des « copies en conflit ».
Marquer le dossier **Toujours conserver sur cet appareil**.

---

## 7. Automatiser le téléchargement

En dernier, parce que c'est la partie la plus fragile. Si elle casse, le dépôt
manuel de l'étape 3 reste le filet de sécurité.

```powershell
playwright install chromium
```

```powershell
playwright codegen https://portail.exemple.interne
```

Relever les sélecteurs et les reporter dans le dictionnaire `SELECTEURS`, en
haut de `src\flash\extract\portail.py`. Tous les sélecteurs sont regroupés là :
quand le portail évolue, il n'y a qu'un seul endroit à corriger.

Le mot de passe n'est jamais écrit dans un fichier du projet — il vit dans le
Gestionnaire d'identification de Windows :

```powershell
python scripts\enregistrer_mot_de_passe.py
```

```powershell
flash extraire
```

En cas d'échec, une capture d'écran et le HTML de la page sont écrits dans
`data\90_sorties\<semaine>\` pour diagnostiquer sans rejouer.

---

## 8. Passer la main à l'utilisateur

```powershell
streamlit run app\streamlit_app.py --server.port 8501
```

Vérifier que l'interface répond sur `http://localhost:8501`, puis installer
les tâches planifiées :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer_taches.ps1
```

Deux tâches sont créées :

- **Flash hebdo - interface** — démarre Streamlit à l'ouverture de session.
  L'utilisateur n'exécute rien : il a un favori navigateur. C'est la réponse
  au blocage des `.bat` par les politiques d'entreprise.
- **Flash hebdo - traitement** — hebdomadaire, **désactivée par défaut**.
  L'activer quand la chaîne est fiable :

```powershell
Enable-ScheduledTask -TaskName "Flash hebdo - traitement"
```

Ces tâches utilisent le chemin complet de l'interpréteur, et non la commande
`flash` : un planificateur n'exécute pas de script d'activation. Ce n'est pas
une lourdeur, c'est la seule forme qui fonctionne sans session interactive.

### Limite du 100 % automatique

Playwright a besoin d'un vrai navigateur, donc d'une session ouverte. Sur un
poste utilisateur, la tâche ne s'exécutera que s'il est allumé et connecté.
Le fonctionnement réellement autonome suppose une VM Windows dédiée et
toujours allumée.

---

## 9. Le cycle hebdomadaire

```powershell
flash run
```

Sans argument, la commande traite la semaine courante : téléchargement,
ingestion, contrôles, mart, classeur, graphiques et brouillon de mail.

Code retour `0` si tout va bien, `1` si les contrôles ont arrêté la
publication — un planificateur peut s'en servir pour alerter.

### En cas de chiffre suspect

Voir [enquete.md](enquete.md). En résumé, trois questions dans l'ordre :

1. Les contrôles disaient-ils déjà quelque chose ?
   `data\90_sorties\<semaine>\controles_qualite.json`
2. La source a-t-elle corrigé le passé ? Les fichiers de
   `data\20_diff\` contiennent les valeurs avant et après, ligne à ligne.
3. Quelles lignes composent ce point ?

```powershell
flash detail --semaine 2026-W37 --ou "categorie = 'Transport' AND mois = '2026-03'"
```

### Surveiller

| Fichier | Contenu |
|---|---|
| `data\_logs\flash.log` | journal détaillé de chaque exécution |
| `data\90_sorties\<semaine>\controles_qualite.json` | résultat des contrôles |
| `data\90_sorties\<semaine>\echec_*.png` | capture si le portail a échoué |

---

## 10. Dépannage

### `No module named flash`

Le paquet n'est pas installé. `flash` n'est pas une bibliothèque à
télécharger : c'est le code du projet, dans `src\flash\`. L'installer revient
à indiquer à Python où le trouver.

```powershell
pip install -e . --no-deps
```

Dépannage immédiat, valable pour la fenêtre en cours uniquement :

```powershell
$env:PYTHONPATH="src"
```

### `does not appear to be a Python project: neither 'setup.py' nor 'pyproject.toml' found`

Le dossier courant n'est pas la racine du projet. Une extraction de ZIP crée
souvent un niveau supplémentaire.

```powershell
Get-ChildItem -Recurse -Depth 3 -Filter pyproject.toml | Where-Object { $_.FullName -notmatch '\\\.venv\\' } | Select-Object -ExpandProperty FullName
```

### `No files were found in testpaths`

Le dossier `tests\` est absent : la copie du projet est incomplète. Revenir à
l'étape 0.

### `module 'flash.…' has no attribute '…'`

Deux causes possibles.

**Le fichier est tronqué.** Revenir à l'étape 0 et relancer
`verifier_integrite.py`.

**Le code exécuté n'est pas celui du dossier courant.** C'est le cas le plus
déroutant : les tests passent mais la commande échoue, parce que ce sont deux
chemins d'import différents. `pytest` lit le code local via
`pythonpath = ["src"]` déclaré dans `pyproject.toml`, tandis que `flash`
importe le paquet **installé** — qui peut pointer vers un ancien dossier.

```powershell
python -c "import os,sys,flash; print('dossier :',os.getcwd()); print('python  :',sys.executable); print('paquet  :',flash.__file__)"
```

Si le chemin du paquet n'est pas celui du dossier courant :

```powershell
pip uninstall flash-hebdo -y
```

```powershell
pip install -e ".[windows,dev]"
```

> Une erreur d'attribut peut en masquer une autre : le gestionnaire
> d'exceptions de `cli.py` référence des classes du module `excel`. Si ce
> module est incomplet, Python échoue en évaluant le gestionnaire et affiche
> cette erreur-là à la place de la vraie.

### `Excel indisponible : …`

Ce n'est pas un échec : la chaîne a basculé sur les graphiques Python et
poursuit. Vérifier qu'Excel est installé, qu'aucune boîte de dialogue n'est
ouverte, et que le classeur n'est pas déjà ouvert dans une autre fenêtre.

### Le script d'activation est bloqué

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Ou passer par `cmd.exe` et `.venv\Scripts\activate.bat`.

---

## 11. Aide-mémoire des commandes

Environnement virtuel activé.

| Commande | Rôle |
|---|---|
| `flash run` | chaîne complète sur la semaine courante |
| `flash run --semaine 2026-W37` | sur une semaine précise |
| `flash etat` | quels fichiers sont disponibles |
| `flash extraire` | télécharger depuis le portail |
| `flash ingerer` | brut → snapshot Parquet figé |
| `flash controler` | contrôles qualité seuls (retour 1 si bloquant) |
| `flash mart` | reconstruire la table agrégée |
| `flash graphiques` | graphiques Python |
| `flash classeur` | classeur Excel : injection, TCD, export PNG |
| `flash mail` | préparer le mail |
| `flash detail --ou "…"` | remonter aux lignes sources d'un chiffre |
| `flash sql "…"` | requête libre sur les snapshots |
| `flash semaines` | historique disponible |
| `flash init` | créer l'arborescence de données |

Options de `run` : `--sans-extraction`, `--sans-mail`, `--sans-excel`,
`--forcer` (publier malgré un contrôle bloquant), `--rapport <nom>`.

| Script | Rôle |
|---|---|
| `python verifier_integrite.py` | contrôler que la copie est complète |
| `python scripts\make_sample_data.py --semaines …` | exports factices |
| `python scripts\make_template.py` | générer le template Excel |
| `python scripts\enregistrer_mot_de_passe.py` | mot de passe dans le trousseau |
| `powershell -ExecutionPolicy Bypass -File scripts\installer_taches.ps1` | tâches planifiées |
