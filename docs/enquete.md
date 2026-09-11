# Quand un graphique paraît faux

Le réflexe naturel est de rouvrir Excel et de refaire les calculs à la main.
La chaîne est construite pour éviter ça : trois questions dans l'ordre, et on
sait en quelques minutes si le problème vient de la source ou du traitement.

## 1. Les contrôles disaient-ils déjà quelque chose ?

```bash
cat data/90_sorties/2026-W37/controles_qualite.json
```

Le fichier liste chaque contrôle, son niveau et son détail chiffré. Une alerte
`valeurs_autorisees` signifie qu'une modalité inconnue est apparue dans la
source ; `variation_volumetrie` qu'il manque ou qu'il y a trop de lignes.
Souvent, la réponse est déjà là.

## 2. La source a-t-elle corrigé le passé ?

C'est la cause la plus fréquente, et la plus déroutante : un chiffre publié en
semaine 34 n'est plus le même vu depuis la semaine 37, alors que personne n'a
touché au traitement. Le portail renvoyant tout l'historique à chaque extraction,
une correction amont réécrit silencieusement le passé.

```bash
python -m flash sql "
  SELECT statut_ligne, count(*) AS n, sum(retroactif::INT) AS sur_le_passe
  FROM read_parquet('data/20_diff/rapport_c/semaine=2026-W37/data.parquet')
  GROUP BY 1 ORDER BY 2 DESC"
```

Le fichier de diff contient, ligne à ligne, les valeurs **avant** et **après** :

```bash
python -m flash sql "
  SELECT id_ligne, montant_avant, montant_apres, statut_avant, statut_apres
  FROM read_parquet('data/20_diff/rapport_c/semaine=2026-W37/data.parquet')
  WHERE statut_ligne = 'modifiee' AND retroactif
  LIMIT 20"
```

Si les corrections sont nombreuses et concentrées sur une période, l'anomalie
vient de la source : c'est un sujet à porter en amont, pas un bug à corriger
dans le pipeline.

## 3. Quelles lignes composent exactement ce point ?

```bash
python -m flash detail --semaine 2026-W37 --ou "categorie = 'Transport' AND mois = '2026-03'"
```

Un classeur est produit avec un onglet par rapport, contenant les lignes
sources et leur identifiant métier — de quoi rouvrir la requête dans le portail
et confronter. Les alias `mois` (`'AAAA-MM'`) et `annee` sont utilisables dans
`--ou`, en plus de toutes les colonnes du schéma.

Cette remontée n'est fiable que parce que le mart est produit **uniquement**
par `transform/sql/mart_flash_hebdo.sql`. Dès qu'un chiffre est retouché à la
main quelque part, le lien entre le graphique et ses lignes sources est rompu.

## 4. Rejouer une semaine

Les fichiers bruts sont archivés horodatés dans `data/00_raw/<semaine>/` et ne
sont jamais modifiés. N'importe quelle semaine peut être reconstruite depuis
zéro, y compris après correction d'un bug de filtrage :

```bash
python -m flash ingerer --semaine 2026-W34
python -m flash mart --semaine 2026-W34
```

Relancer une semaine remplace sa partition : le traitement est idempotent,
relancer deux fois ne duplique rien.

## Comparer deux semaines directement

```bash
python -m flash sql "
  SELECT _semaine, count(*) AS lignes, round(sum(montant)) AS total
  FROM rapport_c_historique
  GROUP BY 1 ORDER BY 1"
```

Cette requête donne, en une ligne par publication, ce que chaque semaine
annonçait. Un décrochage y est immédiatement visible.
