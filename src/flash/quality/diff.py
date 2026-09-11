"""Comparaison de deux snapshots consecutifs.

Le portail renvoyant l'historique complet a chaque extraction, une ligne deja
publiee peut avoir ete corrigee en amont. C'est la premiere cause de
"graphique qui parait faux". Ce module repond a la question : qu'est-ce qui a
change entre l'extraction de la semaine derniere et celle d'aujourd'hui, et
combien de ces changements portent sur des periodes deja publiees.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import Config
from ..ingest.snapshots import COL_HASH, lire_snapshot
from ..logging_setup import journal
from ..paths import Emplacements
from ..weeks import lundi_de

LOG = journal("diff")

AJOUTEE = "ajoutee"
SUPPRIMEE = "supprimee"
MODIFIEE = "modifiee"


@dataclass
class ResultatDiff:
    rapport: str
    semaine: str
    semaine_precedente: str | None
    changements: pd.DataFrame

    @property
    def disponible(self) -> bool:
        return self.semaine_precedente is not None

    def compter(self, statut: str) -> int:
        if self.changements.empty:
            return 0
        return int((self.changements["statut_ligne"] == statut).sum())

    @property
    def retroactifs(self) -> int:
        """Changements portant sur une periode anterieure a la semaine traitee."""
        if self.changements.empty or "retroactif" not in self.changements:
            return 0
        return int(self.changements["retroactif"].sum())

    def resume(self) -> str:
        if not self.disponible:
            return "premiere semaine historisee : aucune comparaison possible"
        return (
            f"{self.compter(AJOUTEE)} ajoutees, "
            f"{self.compter(MODIFIEE)} modifiees, "
            f"{self.compter(SUPPRIMEE)} supprimees "
            f"(dont {self.retroactifs} sur des periodes deja publiees)"
        )


def semaine_precedente_disponible(cfg: Config, rapport: str, semaine: str) -> str | None:
    """Derniere semaine historisee strictement anterieure a ``semaine``."""
    anterieures = [s for s in Emplacements(cfg).semaines_disponibles(rapport) if s < semaine]
    return anterieures[-1] if anterieures else None


def comparer(cfg: Config, rapport: str, semaine: str) -> ResultatDiff:
    schema = cfg.schema(rapport)
    precedente = semaine_precedente_disponible(cfg, rapport, semaine)

    if precedente is None:
        LOG.info("[%s] %s : aucune semaine anterieure, diff ignore", rapport, semaine)
        return ResultatDiff(rapport, semaine, None, pd.DataFrame())

    courant = lire_snapshot(cfg, rapport, semaine)
    ancien = lire_snapshot(cfg, rapport, precedente)

    cles = list(schema.cle.colonnes)
    suivies = list(schema.cle.colonnes_comparees)
    colonne_date = schema.cle.colonne_date

    gauche = ancien[cles + suivies + [colonne_date, COL_HASH]].add_suffix("_avant")
    gauche.columns = cles + [f"{c}_avant" for c in suivies] + [
        f"{colonne_date}_avant", f"{COL_HASH}_avant"
    ]
    droite = courant[cles + suivies + [colonne_date, COL_HASH]].add_suffix("_apres")
    droite.columns = cles + [f"{c}_apres" for c in suivies] + [
        f"{colonne_date}_apres", f"{COL_HASH}_apres"
    ]

    fusion = gauche.merge(droite, on=cles, how="outer", indicator=True)

    fusion["statut_ligne"] = pd.NA
    fusion.loc[fusion["_merge"] == "right_only", "statut_ligne"] = AJOUTEE
    fusion.loc[fusion["_merge"] == "left_only", "statut_ligne"] = SUPPRIMEE
    identiques = (fusion["_merge"] == "both") & (
        fusion[f"{COL_HASH}_avant"] == fusion[f"{COL_HASH}_apres"]
    )
    fusion.loc[(fusion["_merge"] == "both") & ~identiques, "statut_ligne"] = MODIFIEE

    changements = fusion[fusion["statut_ligne"].notna()].drop(columns=["_merge"]).copy()

    if not changements.empty:
        reference = pd.Timestamp(lundi_de(semaine))
        date_ligne = pd.to_datetime(
            changements[f"{colonne_date}_apres"].fillna(changements[f"{colonne_date}_avant"]),
            errors="coerce",
        )
        changements["retroactif"] = (date_ligne < reference) & (
            changements["statut_ligne"] != AJOUTEE
        )
        changements["_semaine_avant"] = precedente
        changements["_semaine_apres"] = semaine

    resultat = ResultatDiff(rapport, semaine, precedente, changements.reset_index(drop=True))
    LOG.info("[%s] %s vs %s : %s", rapport, semaine, precedente, resultat.resume())
    return resultat


def ecrire(cfg: Config, resultat: ResultatDiff) -> None:
    if not resultat.disponible:
        return
    chemin = Emplacements.preparer(Emplacements(cfg).diff(resultat.rapport, resultat.semaine))
    resultat.changements.to_parquet(chemin, index=False, compression="zstd")
    LOG.debug("[%s] diff ecrit : %s", resultat.rapport, chemin)
