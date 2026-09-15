# Modifier l'ancien rapport Excel

Ce document s'adresse à la personne qui fait vivre le rapport Excel
historique. **Aucune connaissance technique n'est nécessaire.** Tout se passe
dans Excel.

---

## Comment ça marche, en une image

```
  templates/classeur/rapport_existant.xlsx        ← LE MODÈLE (votre classeur)
                    │
                    │  le script en fait une copie, puis colle les données
                    ▼
  data/sorties/2026-W38/rapport_existant_2026-W38.xlsx   ← le fichier de la semaine
```

Chaque semaine, le script :

1. fait une **copie** de votre modèle ;
2. colle les données dans trois onglets de cette copie ;
3. laisse tout le reste intact — vos formules, vos mises en forme, vos
   graphiques.

**Votre modèle n'est jamais modifié par le script.** C'est le point le plus
important : vous pouvez le retravailler quand vous voulez sans rien casser.

---

## La règle d'or

> Tout ce que vous voulez voir chaque semaine doit être fait **dans le
> modèle**, jamais dans le fichier de la semaine.

Une modification faite dans `data/sorties/…` disparaîtra à la prochaine
exécution, puisque le fichier est recréé depuis le modèle.

Pour ouvrir le modèle : dossier `templates`, puis `classeur`, puis
`rapport_existant.xlsx`.

---

## Ce que le script remplit

| Onglet | Ce qui y est collé | À partir de |
|---|---|---|
| **Donnees** | les lignes extraites, après filtrage sur la date et le segment | cellule A2 |
| **Objectifs** | un objectif par DR | cellule A2 |
| **Synthese** | le tableau calculé : réalisé, objectif, R/O, écart | cellule A2 |

**La ligne 1 de ces trois onglets n'est jamais touchée.** C'est votre ligne de
titres : elle reste exactement comme vous l'avez écrite.

Tous les autres onglets sont laissés tels quels.

---

## Ce que vous pouvez modifier librement

Vous n'avez prévenir personne pour :

- **changer les couleurs, les polices, les bordures**, la largeur des colonnes ;
- **ajouter un onglet** : un onglet de synthèse, un graphique, une note. Le
  script ne s'occupe que des trois onglets ci-dessus ;
- **ajouter des formules** qui pointent vers les onglets remplis, par exemple
  `=SOMME(Synthese!C:C)`. Elles se recalculeront toutes seules ;
- **ajouter un tableau croisé dynamique** ou un graphique, dans un autre
  onglet, basé sur les données collées ;
- **figer les volets**, ajouter des filtres, masquer des colonnes.

Faites-le dans le modèle, enregistrez, c'est tout.

---

## Ce qu'il ne faut pas faire sans prévenir

Ces trois choses sont **écrites dans la configuration du script**. Si vous les
changez d'un côté sans l'autre, le rapport ne se remplira plus.

### 1. Renommer un des trois onglets

Le script cherche les onglets par leur nom, exactement : `Donnees`,
`Objectifs`, `Synthese`. Un onglet renommé `Données` (avec accent) n'est plus
trouvé.

Ce n'est pas grave et c'est réparable, mais il faut le signaler pour que le
nom soit changé aussi dans la configuration.

### 2. Déplacer la ligne de titres

Le script colle à partir de la **cellule A2**. Si vous insérez une ligne au-
dessus des titres — un logo, un titre de page — les données arriveront au
mauvais endroit.

Deux solutions : mettre votre titre dans un **autre onglet**, ou signaler le
décalage pour que la cellule de départ soit ajustée.

### 3. Ajouter ou déplacer une colonne dans les trois onglets remplis

Les colonnes sont collées dans un ordre fixe. Insérer une colonne au milieu
décale tout.

Si vous avez besoin d'une colonne de calcul personnelle, mettez-la **à droite
de la dernière colonne collée**. Elle ne sera pas écrasée.

---

## Vérifier que tout s'est bien passé

Ouvrez le fichier de la semaine dans `data/sorties/<semaine>/` et regardez :

- l'onglet **Donnees** contient des lignes sous les titres ;
- l'onglet **Synthese** se termine par les lignes **Total toutes DR** et
  **Total hors …** ;
- vos formules affichent des résultats, pas des `#REF!`.

Un `#REF!` signale presque toujours qu'un onglet a été renommé ou supprimé.

---

## Situations courantes

| Vous voulez… | Ce qu'il faut faire |
|---|---|
| Changer les couleurs du tableau | Dans le modèle, comme d'habitude |
| Ajouter un graphique | Dans le modèle, dans n'importe quel onglet |
| Ajouter une colonne de calcul | Dans le modèle, à droite des colonnes collées |
| Ajouter un onglet de synthèse | Dans le modèle, librement |
| Renommer un onglet rempli | Le signaler avant |
| Insérer une ligne au-dessus des titres | Le signaler avant |
| Repartir d'un classeur propre | Remplacer le fichier modèle, en gardant les trois noms d'onglets |

---

## Remplacer le modèle par votre vrai classeur

Le fichier livré est un exemple, et **il n'est pas sauvegardé avec le code** :
le dossier `templates/classeur/` est volontairement exclu, pour qu'un document
interne ne parte jamais par erreur. Pensez donc à garder une copie de votre
modèle ailleurs, comme n'importe quel fichier de travail.

Pour mettre le vôtre à la place :

1. copiez votre classeur dans `templates/classeur/` ;
2. renommez-le `rapport_existant.xlsx`, ou signalez son nom pour que la
   configuration soit ajustée ;
3. vérifiez qu'il contient bien trois onglets nommés `Donnees`, `Objectifs` et
   `Synthese`, avec vos titres en ligne 1 ;
4. **videz les données des semaines précédentes** dans ces trois onglets, en
   gardant la ligne de titres. Le modèle doit être une coquille vide : le
   script la remplit chaque semaine.

---

## Un point à signaler avant la première utilisation

**Si votre classeur contient des tableaux croisés dynamiques ou des macros**,
prévenez la personne qui a installé le script. Il existe deux façons pour lui
d'écrire dans votre classeur, et une seule préserve ces éléments. C'est un
réglage d'une ligne, mais il doit être fait avant la première exécution —
sinon vos tableaux croisés dynamiques disparaîtront de la copie hebdomadaire.

Votre modèle, lui, ne risque rien dans tous les cas.
