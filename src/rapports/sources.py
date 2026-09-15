"""Lecture des fichiers Excel d'entree.

Deux fichiers par rapport : l'extraction du site (toutes les lignes depuis le
debut de l'annee) et le fichier des objectifs (une ligne par DR).

Le principe qui guide ce module : refuser tot et clairement. Un fichier dont
les en-tetes ne correspondent pas a la configuration est rejete avec la liste
des colonnes reellement trouvees, plutot que de produire un rapport faux.
"""

from __future__ import annotations

import fnmatch
import warnings
from pathlib import Path

import pandas as pd

from .config import Rapport
from .journal import journal

LOG = journal("sources")


class FichierIntrouvable(RuntimeError):
    pass


class ColonnesInattendues(RuntimeError):
    pass


def trouver(dossier: Path, motif: str, quoi: str) -> Path:
    """Fichier correspondant au motif. Le plus recent si plusieurs."""
    if not dossier.exists():
        raise FichierIntrouvable(
            f"Dossier introuvable : {dossier}\n  Le creer et y deposer les fichiers."
        )

    candidats = [
        chemin
        for chemin in dossier.iterdir()
        if chemin.is_file()
        and not chemin.name.startswith("~$")  # fichiers temporaires d'Excel
        and fnmatch.fnmatch(chemin.name.lower(), motif.lower())
    ]

    if not candidats:
        presents = sorted(p.name for p in dossier.iterdir() if p.is_file())
        raise FichierIntrouvable(
            f"Aucun fichier {quoi} correspondant a '{motif}' dans {dossier}\n"
            f"  Fichiers presents : {presents or '(dossier vide)'}\n"
            f"  -> corriger le motif dans config/rapports.toml, ou deposer le fichier."
        )

    candidats.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(candidats) > 1:
        LOG.warning(
            "%d fichiers %s correspondent, le plus recent est retenu : %s",
            len(candidats), quoi, candidats[0].name,
        )
    return candidats[0]


def _lire_classeur(chemin: Path, onglet: int | str) -> pd.DataFrame:
    try:
        donnees = pd.read_excel(chemin, sheet_name=onglet)
    except ValueError as exc:
        onglets = pd.ExcelFile(chemin).sheet_names
        raise ColonnesInattendues(
            f"Onglet {onglet!r} introuvable dans {chemin.name}.\n"
            f"  Onglets disponibles : {onglets}"
        ) from exc
    donnees.columns = [str(c).strip() for c in donnees.columns]
    return donnees


def _verifier_colonnes(
    donnees: pd.DataFrame, attendues: dict[str, str], chemin: Path, quoi: str
) -> None:
    presentes = set(donnees.columns)
    manquantes = {role: nom for role, nom in attendues.items() if nom not in presentes}
    if manquantes:
        raise ColonnesInattendues(
            f"Colonnes introuvables dans {chemin.name} ({quoi}) :\n"
            + "".join(f"    role '{r}' -> colonne {n!r} absente\n" for r, n in manquantes.items())
            + f"  Colonnes reellement presentes : {sorted(presentes)}\n"
            f"  -> corriger les noms dans config/rapports.toml (a droite du signe =)."
        )


def lire_source(rapport: Rapport, chemin: Path) -> pd.DataFrame:
    """Extraction du site : une ligne par dossier, depuis le debut de l'annee."""
    donnees = _lire_classeur(chemin, rapport.onglet)
    _verifier_colonnes(donnees, rapport.colonnes, chemin, "fichier source")

    colonnes = [rapport.colonne_date, rapport.colonne_segment, rapport.colonne_dr]
    extrait = donnees[colonnes].copy()

    with warnings.catch_warnings():
        # Les dates viennent d'Excel et sont deja typees dans le cas normal.
        # Quand elles ne le sont pas, pandas previent qu'il devine le format ;
        # c'est exactement le cas que l'on detecte juste apres pour lever une
        # erreur explicite, l'avertissement n'apporte rien a l'utilisateur.
        warnings.simplefilter("ignore", UserWarning)
        dates = pd.to_datetime(extrait[rapport.colonne_date], errors="coerce")
    illisibles = int(dates.isna().sum()) - int(extrait[rapport.colonne_date].isna().sum())
    if illisibles and illisibles == int(extrait[rapport.colonne_date].notna().sum()):
        exemples = [repr(v) for v in extrait[rapport.colonne_date].dropna().head(3)]
        raise ColonnesInattendues(
            f"Aucune valeur de {rapport.colonne_date!r} n'est une date exploitable.\n"
            f"  Valeurs lues : {', '.join(exemples)}\n"
            f"  -> verifier que la colonne designee est bien la bonne."
        )
    if illisibles:
        LOG.warning("%d date(s) illisibles dans %r, ignorees", illisibles, rapport.colonne_date)

    extrait[rapport.colonne_date] = dates
    extrait[rapport.colonne_dr] = extrait[rapport.colonne_dr].astype("string").str.strip()
    extrait[rapport.colonne_segment] = (
        extrait[rapport.colonne_segment].astype("string").str.strip()
    )

    LOG.info("Source %s : %d lignes lues", chemin.name, len(extrait))
    return extrait


def lire_objectifs(rapport: Rapport, chemin: Path) -> pd.DataFrame:
    """Objectifs : une ligne par DR, objectif debut d'annee et objectif annuel."""
    donnees = _lire_classeur(chemin, rapport.objectifs_onglet)
    _verifier_colonnes(donnees, rapport.objectifs_colonnes, chemin, "fichier objectifs")

    roles = rapport.objectifs_colonnes
    extrait = donnees[[roles["dr"], roles["debut_annee"], roles["annuel"]]].copy()
    extrait.columns = ["code_dr", "objectif_debut_annee", "objectif_annuel"]

    extrait["code_dr"] = extrait["code_dr"].astype("string").str.strip()
    for colonne in ("objectif_debut_annee", "objectif_annuel"):
        extrait[colonne] = pd.to_numeric(extrait[colonne], errors="coerce")

    extrait = extrait.dropna(subset=["code_dr"])

    doublons = extrait["code_dr"][extrait["code_dr"].duplicated()].tolist()
    if doublons:
        raise ColonnesInattendues(
            f"Le fichier des objectifs contient plusieurs lignes pour : {sorted(set(doublons))}\n"
            f"  Une seule ligne par DR est attendue."
        )

    LOG.info("Objectifs %s : %d DR", chemin.name, len(extrait))
    return extrait.reset_index(drop=True)
