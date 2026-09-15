# Ajouter un nouveau rapport

Le script traite autant de rapports que nécessaire. Chacun a ses propres
fichiers, ses colonnes, ses filtres et ses objectifs.

**Dans le cas courant, il n'y a aucune ligne de code à écrire** : un bloc à
ajouter dans `config\rapports.toml` suffit.

---

## Le cas courant : même logique, autres fichiers

C'est la situation quand le nouveau rapport se calcule comme le premier —
volume de lignes par DR, filtré sur une date et un segment, confronté à des
objectifs — mais sur un autre fichier, avec d'autres noms de colonnes.

### 1. Ajouter le bloc

À la fin de `config\rapports.toml` :

```toml
[[rapports]]
nom = "resiliations"                    # identifiant court, sans espace
libelle = "Résiliations"                # titre affiché dans les sorties
unite = "résiliations"                  # ce que l'on compte, pour les libellés

fichier = "*resiliation*.xlsx"          # motif de reconnaissance du fichier
onglet = 0                              # 0 = premier onglet, ou "Données"

objectifs_fichier = "*objectifs_resil*.xlsx"
objectifs_onglet = 0

[rapports.colonnes]
date = "Date effet"                     # à droite, l'en-tête EXACT du fichier
segment = "Marché"
dr = "DR"

[rapports.objectifs_colonnes]
dr = "DR"
debut_annee = "Cible YTD"
annuel = "Cible annuelle"

[rapports.filtres]
segments = ["Grand Public"]             # liste vide = aucun filtre

[rapports.totaux]
dr_exclue = ""                          # vide = pas de ligne "Total hors"
```

### 2. Vérifier

```powershell
rapport liste
```

Le nouveau rapport doit apparaître.

```powershell
rapport verifier
```

Les deux fichiers doivent être trouvés. Sinon, corriger les motifs.

### 3. Exécuter

```powershell
rapport run --rapport resiliations
```

Sans `--rapport`, **tous** les rapports configurés sont produits — c'est le
mode normal une fois la mise au point terminée :

```powershell
rapport run
```

Chaque rapport écrit ses propres fichiers dans `data\sorties\<semaine>\`,
préfixés par son `nom`. Ils ne se marchent jamais dessus.

---

## Les champs, un par un

| Champ | Rôle | Défaut |
|---|---|---|
| `nom` | identifiant, sert aussi de préfixe aux fichiers produits | obligatoire |
| `libelle` | titre affiché | le `nom` |
| `unite` | mot employé dans les libellés (« dossiers », « ventes ») | `lignes` |
| `fichier` | motif du fichier source, style `*activite*.xlsx` | obligatoire |
| `onglet` | numéro (0 = premier) ou nom entre guillemets | `0` |
| `objectifs_fichier` | motif du fichier des objectifs | obligatoire |
| `objectifs_onglet` | idem | `0` |
| `colonnes.date` | colonne de date à filtrer | obligatoire |
| `colonnes.segment` | colonne du filtre segment | obligatoire |
| `colonnes.dr` | colonne de regroupement | obligatoire |
| `objectifs_colonnes.*` | les trois colonnes du fichier d'objectifs | obligatoire |
| `filtres.segments` | valeurs conservées ; liste vide = tout garder | `[]` |
| `totaux.dr_exclue` | DR sortie du second total ; vide = pas de ligne | `""` |

À gauche du signe `=`, le **rôle** attendu par le script — ne jamais le
changer. À droite, l'**en-tête exact** de votre fichier, accents et espaces
compris.

Si un nom ne correspond pas, l'exécution s'arrête et liste les colonnes
réellement présentes dans le fichier. Il n'y a plus qu'à recopier.

---

## Ce qui n'est pas paramétrable

Le bloc `[[rapports]]` couvre la logique « compter des lignes par DR et
comparer à un objectif ». Trois choses sortent de ce cadre et demandent du
code.

### Compter autre chose qu'un nombre de lignes

Aujourd'hui la mesure est le **nombre de lignes**. Pour sommer un montant, il
faut modifier `src\rapports\calculs.py` : dans la section « Volumes par DR »,
remplacer `.size()` par `[colonne].sum()`. La façon propre est d'ajouter un
champ `mesure` à la configuration, avec `"lignes"` comme valeur par défaut, et
de faire porter le choix dessus — le reste de la chaîne n'a pas à changer.

### Filtrer sur un troisième champ

`[rapports.filtres]` ne connaît que `segments`. Pour filtrer aussi sur, par
exemple, un type de contrat, il faut ajouter le champ à `Rapport`
(`src\rapports\config.py`) et un filtre dans `calculs.calculer`.

### Regrouper par autre chose qu'une DR

La colonne de regroupement est déjà paramétrable : `colonnes.dr` peut désigner
n'importe quelle colonne — une région, une agence, un produit. Seuls les
libellés affichés parlent encore de « DR ».

---

## Ajouter une colonne au tableau de sortie

Les colonnes affichées sont définies à trois endroits, à garder alignés :

| Fichier | À modifier |
|---|---|
| `src\rapports\calculs.py` | la liste `COLONNES` et le calcul dans `calculer` |
| `src\rapports\sorties\excel.py` | la liste `COLONNES` (champ, en-tête, format, largeur) |
| `src\rapports\sorties\html.py` | `ENTETES` et la fonction `_ligne`, plus la ligne `<td>` du gabarit |

Le gabarit HTML est `templates\rapport.html.j2`.

---

## Avant de considérer que c'est fini

```powershell
pytest
```

Les 33 tests existants vérifient les règles de calcul : périmètre de la
semaine, périmètre du cumul, filtres, et surtout le fait que le R/O des
totaux est recalculé à partir des sommes et non moyenné. Si vous touchez à
`calculs.py`, ce sont eux qui vous diront si une règle a été cassée.

Pour un nouveau comportement, ajouter un test dans `tests\test_calculs.py` :
les fabriques de `tests\fabrique.py` permettent de construire un jeu de
données en trois lignes.
