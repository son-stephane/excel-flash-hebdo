-- ===========================================================================
-- MART HEBDOMADAIRE -- c'est ICI que vit la logique metier.
--
-- Regle a tenir : le mart est produit uniquement par ce SQL, jamais par des
-- manipulations manuelles. C'est ce qui rend chaque point de graphique
-- reproductible, et donc enquetable (voir `flash detail`).
--
-- Vues disponibles (creees par transform/marts.py) :
--   rapport_a, rapport_b, rapport_c              -> snapshot de la semaine traitee
--   rapport_a_historique, ...                    -> tous les snapshots, colonne _semaine
--
-- Parametre : $semaine  (ex. '2026-W37')
-- ===========================================================================

WITH unifie AS (
    SELECT 'A' AS perimetre, date_operation, entite, categorie,
           CAST(NULL AS VARCHAR) AS sous_categorie, statut, montant, quantite
    FROM rapport_a

    UNION ALL
    SELECT 'B', date_operation, entite, categorie,
           CAST(NULL AS VARCHAR), statut, montant, quantite
    FROM rapport_b

    UNION ALL
    SELECT 'C', date_operation, entite, categorie,
           sous_categorie, statut, montant, quantite
    FROM rapport_c
)
SELECT
    $semaine                                   AS semaine_publication,
    date_trunc('month', date_operation)::DATE  AS mois,
    perimetre,
    entite,
    categorie,
    statut,
    COUNT(*)                                   AS nb_operations,
    SUM(montant)                               AS montant_total,
    AVG(montant)                               AS montant_moyen,
    SUM(COALESCE(quantite, 0))                 AS quantite_totale
FROM unifie
WHERE date_operation IS NOT NULL
GROUP BY ALL
ORDER BY mois, perimetre, entite, categorie, statut
