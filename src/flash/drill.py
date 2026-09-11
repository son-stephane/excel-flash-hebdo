"""Remontee aux lignes sources derriere un point de graphique.

Usage typique quand un chiffre parait faux :

    flash detail --semaine 2026-W37 --ou "categorie = 'Transport' AND mois = '2026-03'"

Le fichier produit contient les lignes exactes de l'export du portail qui
composent le point, avec leur identifiant metier : de quoi rouvrir la requete
dans le portail et confronter.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .config import Config
from .logging_setup import journal
from .paths import Emplacements
from .transform.marts import connexion

LOG = journal("detail")

# Alias pratiques utilisables dans --ou, traduits en SQL avant execution.
ALIAS = {
    "mois": "strftime(date_operation, '%Y-%m')",
    "annee": "strftime(date_operation, '%Y')",
}


def _traduire(filtre: str) -> str:
    resultat = filtre
    for alias, expression in ALIAS.items():
        # Remplacement mot entier uniquement, pour ne pas casser une colonne
        # dont le nom contiendrait l'alias.
        resultat = _remplacer_mot(resultat, alias, expression)
    return resultat


def _remplacer_mot(texte: str, mot: str, remplacement: str) -> str:
    import re

    return re.sub(rf"(?<![\w.]){re.escape(mot)}(?![\w(])", remplacement, texte)


def detailler(
    cfg: Config,
    semaine: str,
    filtre: str,
    *,
    rapports: list[str] | None = None,
    limite: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Retourne, par rapport, les lignes sources correspondant au filtre."""
    condition = _traduire(filtre)
    resultats: dict[str, pd.DataFrame] = {}

    with connexion(cfg, semaine) as con:
        for nom in rapports or cfg.rapports:
            requete = f"SELECT * FROM {nom} WHERE {condition}"
            if limite:
                requete += f" LIMIT {limite}"
            try:
                lignes = con.execute(requete).df()
            except duckdb.CatalogException:
                LOG.debug("[%s] pas de snapshot pour %s, ignore", nom, semaine)
                continue
            except duckdb.BinderException as exc:
                LOG.warning("[%s] filtre inapplicable (%s)", nom, str(exc).split("\n")[0])
                continue
            if not lignes.empty:
                resultats[nom] = lignes
                LOG.info("[%s] %d ligne(s) correspondantes", nom, len(lignes))

    if not resultats:
        LOG.warning("Aucune ligne ne correspond a : %s", filtre)
    return resultats


def exporter(
    cfg: Config, semaine: str, resultats: dict[str, pd.DataFrame], sortie: Path | None = None
) -> Path:
    """Ecrit un classeur avec un onglet par rapport."""
    lieux = Emplacements(cfg)
    chemin = sortie or (lieux.sorties(semaine) / f"detail_{semaine}.xlsx")
    Emplacements.preparer(chemin)

    if not resultats:
        vide = pd.DataFrame({"resultat": ["aucune ligne ne correspond au filtre"]})
        resultats = {"vide": vide}

    with pd.ExcelWriter(chemin, engine="openpyxl") as classeur:
        for nom, lignes in resultats.items():
            lignes.to_excel(classeur, sheet_name=nom[:31], index=False)

    LOG.info("Detail exporte : %s", chemin)
    return chemin
