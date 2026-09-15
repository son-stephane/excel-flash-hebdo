# Exécuter le rapport

Ce document couvre l'installation et l'exécution hebdomadaire. Pour ajouter un
deuxième rapport, voir [ajouter-un-rapport.md](ajouter-un-rapport.md).

---

## 1. Installation (une seule fois)

Depuis la racine du projet, dans PowerShell :

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\Activate.ps1
```

L'invite se préfixe de `(.venv)`. Si la politique d'exécution bloque
l'activation, lever la restriction pour la fenêtre courante — sans droits
administrateur et sans modification durable du poste :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

```powershell
pip install -e ".[dev]"
```

Cette commande installe **les dépendances et le projet**. C'est elle qui rend
la commande `rapport` disponible.

Vérifier :

```powershell
pytest
```

33 tests verts.

> **L'activation ne vaut que pour la fenêtre PowerShell en cours.** À chaque
> nouvelle session, refaire `.venv\Scripts\Activate.ps1`. Sans activation, les
> commandes s'écrivent `.venv\Scripts\python.exe -m rapports …`.

---

## 2. Essayer sans les vrais fichiers

Un générateur produit deux classeurs d'exemple ayant la structure attendue :

```powershell
python scripts\generer_exemple.py
```

```powershell
rapport run
```

Les sorties arrivent dans `data\sorties\<semaine>\`. Ouvrir le `.html` dans un
navigateur et le `.xlsx` dans Excel pour voir à quoi ressemble le résultat.

Effacer ensuite les fichiers d'exemple :

```powershell
Remove-Item data\entrees\*.xlsx
```

---

## 3. Brancher les vrais fichiers

Déposer dans `data\entrees\` les deux classeurs : l'extraction du site et le
fichier des objectifs.

```powershell
rapport verifier
```

Cette commande dit, pour chaque fichier attendu, s'il est trouvé. Si un
fichier apparaît `manquant`, c'est que le **motif** ne correspond pas au nom
réel — corriger `fichier` ou `objectifs_fichier` dans `config\rapports.toml`.

Puis adapter les noms de colonnes, toujours dans `config\rapports.toml` :

```toml
[rapports.colonnes]
date = "Date CAV"        # à gauche le rôle, à droite l'en-tête exact du fichier
segment = "Segment"
dr = "Code DR"
```

Si un en-tête ne correspond pas, l'exécution s'arrête et **liste les colonnes
réellement présentes** dans le fichier — il n'y a plus qu'à recopier :

```
Colonnes introuvables dans activite_2026.xlsx (fichier source) :
    role 'dr' -> colonne 'Code DR' absente
  Colonnes reellement presentes : ['Date CAV', 'Direction regionale', 'Segment']
  -> corriger les noms dans config/rapports.toml (a droite du signe =).
```

Enfin, les segments à conserver et la DR à sortir du total :

```toml
[rapports.filtres]
segments = ["Grand Public", "Pro"]

[rapports.totaux]
dr_exclue = "DR99"
```

---

## 4. L'exécution hebdomadaire

```powershell
rapport run
```

Sans argument, la semaine ISO courante est traitée. Pour rejouer une semaine
précise — le fichier contenant toute l'année, n'importe quelle semaine passée
est reconstituable :

```powershell
rapport run --semaine 2026-W37
```

Trois fichiers sont produits dans `data\sorties\<semaine>\` :

| Fichier | Contenu |
|---|---|
| `<rapport>_<semaine>.html` | page autonome : tableau et graphique, aucune ressource externe |
| `<rapport>_<semaine>.xlsx` | tableau formaté et **vrai** graphique Excel, modifiable |
| `<rapport>_<semaine>.png` | le graphique seul, si besoin de l'insérer ailleurs |

Relancer la même semaine écrase les fichiers : le traitement est rejouable
sans rien dupliquer.

---

## 5. Lire le résultat

Le tableau comporte une ligne par DR, puis deux lignes de total.

| Colonne | Signification |
|---|---|
| Réalisé semaine | lignes dont la date tombe dans les 7 jours de la semaine |
| Réalisé cumul | lignes du 1er janvier au dimanche de la semaine |
| Objectif début année | valeur lue dans le fichier des objectifs |
| **R/O** | **réalisé cumul ÷ objectif début année** |
| Écart | réalisé cumul − objectif début année |
| Objectif annuel | valeur lue dans le fichier des objectifs |
| % objectif annuel | où en est le cumul par rapport à l'année entière |

Deux points qui évitent les malentendus :

**Le R/O porte sur le cumul, pas sur la semaine.** Comparer sept jours à un
objectif début d'année n'aurait pas de sens. La colonne « Réalisé semaine »
reste affichée pour suivre l'activité, mais elle n'entre dans aucun ratio.

**Le R/O des lignes de total est recalculé à partir des sommes**, jamais
obtenu en moyennant les R/O des DR — une moyenne de ratios de poids différents
ne veut rien dire.

---

## 6. Messages d'avertissement

Ils apparaissent en console, dans le bloc « Points de vigilance » du HTML, et
dans `data\sorties\_journal\rapports.log`. Ils ne bloquent pas l'exécution
mais méritent un regard.

| Message | Cause probable |
|---|---|
| `DR présentes dans les données mais absentes des objectifs` | une DR nouvelle, ou un code écrit différemment dans les deux fichiers |
| `n ligne(s) postérieures au …` | normal si vous rejouez une semaine passée |
| `Segment(s) demandés absents du fichier` | libellé de segment changé à la source |
| `DR à exclure du total introuvable` | `dr_exclue` ne correspond à aucun code présent |

---

## 7. Dépannage

**`No module named rapports`** — le projet n'est pas installé. `pip install -e
".[dev]"` depuis la racine. Dépannage immédiat : `$env:PYTHONPATH="src"`.

**`rapport : terme non reconnu`** — l'environnement n'est pas activé. Faire
`.venv\Scripts\Activate.ps1`, ou écrire `.venv\Scripts\python.exe -m rapports`.

**Un fichier verrouillé par Excel** — les fichiers `~$...xlsx` créés par Excel
quand un classeur est ouvert sont automatiquement ignorés. En revanche, une
sortie ne peut pas être réécrite si elle est ouverte : fermer le classeur
avant de relancer.

**Les chiffres ne correspondent pas à ceux calculés à la main** — vérifier
dans cet ordre : le segment filtré, la semaine demandée, et le fait que le
R/O porte sur le cumul et non sur la semaine.
