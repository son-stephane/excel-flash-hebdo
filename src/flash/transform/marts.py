"""Transformation : snapshots Parquet -> table agregee prete a publier.

DuckDB lit directement les fichiers Parquet, sans serveur ni import prealable.
Le SQL metier vit dans ``transform/sql/`` : il est versionne, relisible, et
c'est la seule definition des chiffres publies.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from ..config import Config
from ..logging_setup import journal
from ..paths import Emplacements

LOG = journal("mart")

DOSSIER_SQL = Path(__file__).parent / "sql"


def connexion(cfg: Config, semaine: str | None = None) -> duckdb.DuckDBPyConnection:
    """Connexion DuckDB en memoire, avec les vues sur les snapshots.

    Pour chaque rapport, deux vues :
      * ``<rapport>``              -- le snapshot de la semaine demandee
      * ``<rapport>_historique``   -- tous les snapshots empiles
    Plus une vue ``marts`` sur l'ensemble des marts deja produits.
    """
    lieux = Emplacements(cfg)
    con = duckdb.connect()

    for rapport in cfg.rapports:
        motif = lieux.snapshots_glob(rapport)
        if not lieux.semaines_disponibles(rapport):
            LOG.debug("[%s] aucun snapshot, vue non creee", rapport)
            continue
        con.execute(
            f"CREATE VIEW {rapport}_historique AS "
            f"SELECT * FROM read_parquet('{motif}', union_by_name=true)"
        )
        if semaine:
            con.execute(
                f"CREATE VIEW {rapport} AS "
                f"SELECT * FROM {rapport}_historique WHERE _semaine = '{semaine}'"
            )

    marts = sorted(Path(p) for p in _lister_marts(lieux))
    if marts:
        con.execute(
            f"CREATE VIEW marts AS SELECT * FROM read_parquet('{lieux.mart_glob()}', "
            f"union_by_name=true)"
        )
    return con


def _lister_marts(lieux: Emplacements) -> list[str]:
    dossier = lieux.racine / "30_mart"
    if not dossier.exists():
        return []
    return [str(p) for p in dossier.glob("semaine=*/data.parquet")]


def lire_sql(nom: str) -> str:
    chemin = DOSSIER_SQL / f"{nom}.sql"
    if not chemin.exists():
        disponibles = ", ".join(p.stem for p in DOSSIER_SQL.glob("*.sql"))
        raise FileNotFoundError(f"Requete inconnue : {nom}. Disponibles : {disponibles}")
    return chemin.read_text(encoding="utf-8")


def construire(cfg: Config, semaine: str, *, requete: str = "mart_flash_hebdo") -> pd.DataFrame:
    """Execute le SQL du mart et ecrit le resultat dans la partition de la semaine."""
    with connexion(cfg, semaine) as con:
        table = con.execute(lire_sql(requete), {"semaine": semaine}).df()

    chemin = Emplacements.preparer(Emplacements(cfg).mart(semaine))
    table.to_parquet(chemin, index=False, compression="zstd")
    LOG.info("Mart %s : %d lignes agregees -> %s", semaine, len(table), chemin.name)
    return table


def lire_mart(cfg: Config, semaine: str) -> pd.DataFrame:
    chemin = Emplacements(cfg).mart(semaine)
    if not chemin.exists():
        raise FileNotFoundError(
            f"Pas de mart pour {semaine}. Lancer : flash mart --semaine {semaine}"
        )
    return pd.read_parquet(chemin)


def evolution(cfg: Config) -> pd.DataFrame:
    """Serie multi-semaines, pour les graphiques de tendance."""
    with connexion(cfg) as con:
        try:
            return con.execute(lire_sql("evolution")).df()
        except duckdb.CatalogException:
            LOG.warning("Aucun mart disponible : evolution vide")
            return pd.DataFrame(columns=["semaine_publication", "perimetre", "nb_operations", "montant_total"])


def requete_libre(cfg: Config, sql: str, semaine: str | None = None) -> pd.DataFrame:
    """Execute une requete ad hoc sur les vues -- utilisee par `flash sql`."""
    with connexion(cfg, semaine) as con:
        parametres = {"semaine": semaine} if semaine and "$semaine" in sql else None
        return con.execute(sql, parametres).df() if parametres else con.execute(sql).df()
