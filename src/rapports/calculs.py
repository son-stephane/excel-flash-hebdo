"""Coeur du calcul : filtrage, comptage par DR, confrontation aux objectifs.

Deux mesures de realise coexistent volontairement :

  * le realise de la SEMAINE -- l'activite des sept jours ;
  * le realise CUMULE depuis le 1er janvier -- la seule grandeur comparable a
    un objectif debut d'annee.

Le R/O et l'ecart portent donc sur le cumul. Comparer une semaine a un
objectif annuel n'aurait aucun sens.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Rapport
from .journal import journal
from .semaines import bornes, debut_annee

LOG = journal("calculs")

LIGNE_DR = "dr"
LIGNE_TOTAL = "total"
LIGNE_TOTAL_HORS = "total_hors"

COLONNES = [
    "code_dr",
    "realise_semaine",
    "realise_cumul",
    "objectif_debut_annee",
    "ro",
    "ecart",
    "objectif_annuel",
    "part_annuel",
    "type_ligne",
]


@dataclass
class Resultat:
    rapport: Rapport
    semaine: str
    tableau: pd.DataFrame
    lignes_lues: int
    lignes_apres_filtre: int
    avertissements: list[str] = field(default_factory=list)

    @property
    def par_dr(self) -> pd.DataFrame:
        return self.tableau[self.tableau["type_ligne"] == LIGNE_DR]

    @property
    def total(self) -> pd.Series | None:
        lignes = self.tableau[self.tableau["type_ligne"] == LIGNE_TOTAL]
        return lignes.iloc[0] if len(lignes) else None

    def resume(self) -> str:
        total = self.total
        if total is None:
            return "aucune donnee"
        ro = "n/a" if pd.isna(total["ro"]) else f"{total['ro']:.1%}"
        return (
            f"{len(self.par_dr)} DR - "
            f"{int(total['realise_cumul'])} cumul / "
            f"{_entier(total['objectif_debut_annee'])} objectif - R/O {ro}"
        )


def _entier(valeur) -> str:
    return "n/a" if pd.isna(valeur) else str(int(valeur))


def _ratio(numerateur: pd.Series, denominateur: pd.Series) -> pd.Series:
    """Division protegee : un objectif nul ou absent donne un resultat vide,
    jamais une division par zero ni un ratio aberrant."""
    denominateur = pd.to_numeric(denominateur, errors="coerce")
    return pd.Series(
        np.where(
            (denominateur.notna()) & (denominateur != 0),
            pd.to_numeric(numerateur, errors="coerce") / denominateur.replace(0, np.nan),
            np.nan,
        ),
        index=numerateur.index,
        dtype="float64",
    )


def calculer(
    rapport: Rapport, source: pd.DataFrame, objectifs: pd.DataFrame, semaine: str
) -> Resultat:
    lignes_lues = len(source)
    avertissements: list[str] = []

    # --- 1. Filtre sur le segment ----------------------------------------
    retenu = source
    if rapport.segments:
        connus = set(source[rapport.colonne_segment].dropna().unique())
        inconnus = [s for s in rapport.segments if s not in connus]
        if inconnus:
            message = (
                f"Segment(s) demandes absents du fichier : {inconnus}. "
                f"Valeurs presentes : {sorted(connus)}"
            )
            avertissements.append(message)
            LOG.warning(message)
        retenu = source[source[rapport.colonne_segment].isin(list(rapport.segments))]
        LOG.info(
            "Filtre segment %s : %d lignes sur %d conservees",
            list(rapport.segments), len(retenu), lignes_lues,
        )

    if retenu.empty:
        avertissements.append("Aucune ligne ne passe le filtre segment.")

    # --- 2. Filtres sur la date ------------------------------------------
    lundi, dimanche = bornes(semaine)
    premier_janvier = debut_annee(semaine)
    dates = retenu[rapport.colonne_date]

    dans_la_semaine = (dates >= pd.Timestamp(lundi)) & (dates <= pd.Timestamp(dimanche))
    dans_le_cumul = (dates >= pd.Timestamp(premier_janvier)) & (
        dates <= pd.Timestamp(dimanche)
    )

    posterieures = int((dates > pd.Timestamp(dimanche)).sum())
    if posterieures:
        message = (
            f"{posterieures} ligne(s) posterieures au {dimanche:%d/%m/%Y} ecartees "
            f"(le fichier contient des donnees plus recentes que la semaine demandee)"
        )
        avertissements.append(message)
        LOG.warning(message)

    # --- 3. Volumes par DR ------------------------------------------------
    dr = rapport.colonne_dr
    volumes = pd.DataFrame(
        {
            "realise_semaine": retenu[dans_la_semaine].groupby(dr).size(),
            "realise_cumul": retenu[dans_le_cumul].groupby(dr).size(),
        }
    )
    volumes.index.name = "code_dr"
    volumes = volumes.reset_index()

    # --- 4. Jonction avec les objectifs -----------------------------------
    tableau = volumes.merge(objectifs, on="code_dr", how="outer", indicator=True)

    sans_objectif = sorted(tableau.loc[tableau["_merge"] == "left_only", "code_dr"])
    sans_activite = sorted(tableau.loc[tableau["_merge"] == "right_only", "code_dr"])
    if sans_objectif:
        message = f"DR presentes dans les donnees mais absentes des objectifs : {sans_objectif}"
        avertissements.append(message)
        LOG.warning(message)
    if sans_activite:
        LOG.info("DR sans activite sur la periode : %s", sans_activite)

    tableau = tableau.drop(columns=["_merge"])
    for colonne in ("realise_semaine", "realise_cumul"):
        tableau[colonne] = tableau[colonne].fillna(0).astype(int)

    # --- 5. Indicateurs ---------------------------------------------------
    tableau["ro"] = _ratio(tableau["realise_cumul"], tableau["objectif_debut_annee"])
    tableau["ecart"] = tableau["realise_cumul"] - tableau["objectif_debut_annee"]
    tableau["part_annuel"] = _ratio(tableau["realise_cumul"], tableau["objectif_annuel"])
    tableau["type_ligne"] = LIGNE_DR
    tableau = tableau.sort_values("code_dr").reset_index(drop=True)

    # --- 6. Totaux --------------------------------------------------------
    lignes_totaux = [_agreger(tableau, "Total toutes DR", LIGNE_TOTAL)]
    if rapport.dr_exclue:
        if rapport.dr_exclue in set(tableau["code_dr"]):
            restant = tableau[tableau["code_dr"] != rapport.dr_exclue]
            lignes_totaux.append(
                _agreger(restant, f"Total hors {rapport.dr_exclue}", LIGNE_TOTAL_HORS)
            )
        else:
            message = (
                f"DR a exclure du total introuvable : {rapport.dr_exclue!r}. "
                f"Ligne 'Total hors' non produite."
            )
            avertissements.append(message)
            LOG.warning(message)

    complet = pd.concat([tableau, pd.DataFrame(lignes_totaux)], ignore_index=True)

    resultat = Resultat(
        rapport=rapport,
        semaine=semaine,
        tableau=complet[COLONNES],
        lignes_lues=lignes_lues,
        lignes_apres_filtre=len(retenu),
        avertissements=avertissements,
    )
    LOG.info("Resultat : %s", resultat.resume())
    return resultat


def _agreger(tableau: pd.DataFrame, libelle: str, type_ligne: str) -> dict:
    """Ligne de total.

    Le R/O du total est recalcule a partir des sommes, jamais obtenu en
    moyennant les R/O des DR : une moyenne de ratios ne veut rien dire des
    qu'elles n'ont pas le meme poids.
    """
    cumul = int(tableau["realise_cumul"].sum())
    objectif = tableau["objectif_debut_annee"].sum(min_count=1)
    annuel = tableau["objectif_annuel"].sum(min_count=1)
    valide = pd.notna(objectif) and objectif != 0

    return {
        "code_dr": libelle,
        "realise_semaine": int(tableau["realise_semaine"].sum()),
        "realise_cumul": cumul,
        "objectif_debut_annee": objectif,
        "ro": (cumul / objectif) if valide else np.nan,
        "ecart": (cumul - objectif) if pd.notna(objectif) else np.nan,
        "objectif_annuel": annuel,
        "part_annuel": (cumul / annuel) if pd.notna(annuel) and annuel != 0 else np.nan,
        "type_ligne": type_ligne,
    }
