-- ===========================================================================
-- SERIE D'EVOLUTION entre publications successives.
-- Lit les marts deja produits : chaque semaine de publication apporte sa
-- propre vision de l'historique, ce qui rend visibles les revisions.
--
-- Vue disponible : marts (union de tous les marts hebdomadaires)
-- ===========================================================================

SELECT
    semaine_publication,
    perimetre,
    SUM(nb_operations)  AS nb_operations,
    SUM(montant_total)  AS montant_total
FROM marts
GROUP BY ALL
ORDER BY semaine_publication, perimetre
