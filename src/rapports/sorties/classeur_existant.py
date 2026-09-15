"""Remplissage du classeur historique -- celui rempli aujourd'hui a la main.

Le script colle les memes blocs, dans les memes onglets, aux memes endroits.
Le reste du classeur -- formules, TCD, graphiques, mise en forme -- n'est pas
touche.

Le modele a tout interet a ne contenir que ses lignes d'en-tete : la copie
repart de lui chaque semaine, donc il n'y a alors rien a effacer. L'option
"effacer_avant" ne sert que si le modele contient deja des donnees. Elle vide
les cellules sans supprimer les lignes, pour ne rien decaler autour.

Deux moteurs d'ecriture, parce qu'ils n'ont pas les memes garanties :

  * EXCEL (xlwings) pilote le vrai Excel. Tout est preserve, y compris les
    tableaux croises dynamiques et les graphiques. C'est le moteur a utiliser
    sur un classeur qui en contient.
  * OPENPYXL ecrit le fichier directement, sans Excel. Portable et rapide,
    mais il REECRIT le classeur : les tableaux croises dynamiques, certains
    objets graphiques et les macros peuvent etre perdus.

Le moteur "auto" essaie Excel, et bascule sur openpyxl en prevenant.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from openpyxl.utils import coordinate_to_tuple

from ..calculs import Resultat
from ..config import OngletCollage
from ..journal import journal
from . import style

LOG = journal("classeur")

# Delai au-dela duquel on cesse d'attendre Excel. Un classeur qui ouvre une
# boite de dialogue au demarrage -- fichier recupere, macro a autoriser, mise
# a jour de liaisons -- bloque le pilotage indefiniment. Un traitement
# hebdomadaire ne doit jamais rester suspendu a ca.
DELAI_EXCEL_S = 90

ENTETES_SYNTHESE = [
    "Code DR", "Realise semaine", "Realise cumul", "Objectif debut annee",
    "R/O", "Ecart", "Objectif annuel", "% objectif annuel",
]


class ClasseurIndisponible(RuntimeError):
    pass


@dataclass
class ResultatCollage:
    chemin: Path
    moteur: str
    onglets: list[str] = field(default_factory=list)
    lignes: int = 0
    avertissements: list[str] = field(default_factory=list)

    def resume(self) -> str:
        return (
            f"{len(self.onglets)} onglet(s) remplis ({', '.join(self.onglets)}), "
            f"{self.lignes} ligne(s) au total, moteur {self.moteur}"
        )


# --------------------------------------------------------------------------
# Quel bloc de donnees va dans quel onglet
# --------------------------------------------------------------------------
def bloc(resultat: Resultat, contenu: str) -> pd.DataFrame:
    if contenu == "donnees":
        return resultat.donnees_filtrees
    if contenu == "objectifs":
        objectifs = resultat.objectifs.copy()
        objectifs.columns = ["Code DR", "Objectif debut annee", "Objectif annuel"]
        return objectifs
    if contenu == "synthese":
        synthese = resultat.tableau.drop(columns=["type_ligne"]).copy()
        synthese.columns = ENTETES_SYNTHESE
        return synthese
    raise ClasseurIndisponible(f"Contenu inconnu : {contenu!r}")


def _valeurs(donnees: pd.DataFrame, avec_entetes: bool) -> list[list]:
    """Convertit en types que les deux moteurs savent ecrire."""
    lignes: list[list] = []
    if avec_entetes:
        lignes.append([str(c) for c in donnees.columns])
    for enregistrement in donnees.itertuples(index=False):
        lignes.append([_valeur(v) for v in enregistrement])
    return lignes


def _valeur(valeur):
    if pd.isna(valeur):
        return None
    if isinstance(valeur, pd.Timestamp):
        return valeur.to_pydatetime()
    if hasattr(valeur, "item"):  # types numpy
        return valeur.item()
    return valeur


# --------------------------------------------------------------------------
def remplir(
    resultats: dict[str, Resultat],
    onglets: tuple[OngletCollage, ...],
    modele: Path,
    destination: Path,
    moteur: str = "auto",
) -> ResultatCollage:
    if not modele.exists():
        raise ClasseurIndisponible(
            f"Modele introuvable : {modele}\n"
            f"  Deposer votre classeur a cet emplacement, ou en generer un "
            f"d'exemple : python scripts/generer_modele_classeur.py"
        )

    if destination.resolve() == modele.resolve():
        raise ClasseurIndisponible(
            f"Le modele et la sortie designent le meme fichier : {modele}\n"
            f"  Le modele ne doit jamais etre ecrit : il sert de point de depart "
            f"a chaque semaine."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(modele, destination)  # le modele n'est jamais modifie

    blocs = []
    for onglet in onglets:
        resultat = resultats.get(onglet.rapport)
        if resultat is None:
            LOG.warning(
                "Onglet '%s' ignore : le rapport '%s' n'a pas ete produit",
                onglet.onglet, onglet.rapport,
            )
            continue
        blocs.append((onglet, bloc(resultat, onglet.contenu)))

    if moteur in ("auto", "excel"):
        try:
            return _avec_delai(blocs, destination)
        except ClasseurIndisponible as exc:
            if moteur == "excel":
                raise
            LOG.warning("Excel non pilotable (%s)", exc)
            LOG.warning(
                "Bascule sur openpyxl. Attention : les tableaux croises dynamiques "
                "et les macros eventuels du classeur ne survivront pas. Pour les "
                "preserver, corriger Excel puis forcer moteur = \"excel\"."
            )
            # On repart du modele : la tentative precedente a pu laisser la
            # copie dans un etat intermediaire.
            shutil.copy2(modele, destination)

    return _via_openpyxl(blocs, destination)


def _avec_delai(blocs, destination: Path) -> ResultatCollage:
    """Tente le pilotage d'Excel sans risquer de suspendre le traitement."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executeur:
        tache = executeur.submit(_via_excel, blocs, destination)
        try:
            return tache.result(timeout=DELAI_EXCEL_S)
        except concurrent.futures.TimeoutError:
            executeur.shutdown(wait=False)
            raise ClasseurIndisponible(
                f"Excel n'a pas repondu en {DELAI_EXCEL_S} s. Une boite de dialogue "
                f"est probablement ouverte (fichier protege, liaisons a mettre a "
                f"jour, macro a autoriser). Fermer Excel et reessayer."
            ) from None


# --------------------------------------------------------------------------
def _via_excel(blocs, destination: Path) -> ResultatCollage:
    """Pilote le vrai Excel : rien d'autre dans le classeur n'est altere."""
    try:
        import xlwings as xw
    except ImportError as exc:
        raise ClasseurIndisponible("xlwings n'est pas installe") from exc

    resultat = ResultatCollage(chemin=destination, moteur="Excel")
    application = None
    classeur = None
    try:
        application = xw.App(visible=False, add_book=False)
        application.display_alerts = False
        application.screen_updating = False
        classeur = application.books.open(str(destination))
        noms = [f.name for f in classeur.sheets]

        for onglet, donnees in blocs:
            if onglet.onglet not in noms:
                resultat.avertissements.append(
                    f"Onglet '{onglet.onglet}' absent du classeur (present : {noms})"
                )
                LOG.warning("%s", resultat.avertissements[-1])
                continue

            feuille = classeur.sheets[onglet.onglet]
            if onglet.effacer_avant:
                _effacer_excel(feuille, onglet.cellule, donnees.shape[1])

            valeurs = _valeurs(donnees, onglet.avec_entetes)
            if valeurs:
                feuille.range(onglet.cellule).value = valeurs
            resultat.onglets.append(onglet.onglet)
            resultat.lignes += len(donnees)
            LOG.info("[%s] %d ligne(s) collees en %s", onglet.onglet, len(donnees), onglet.cellule)

        classeur.save()
    except Exception as exc:
        raise ClasseurIndisponible(str(exc)) from exc
    finally:
        if classeur is not None:
            classeur.close()
        if application is not None:
            application.quit()

    return resultat


def _effacer_excel(feuille, cellule: str, largeur: int) -> None:
    """Vide la zone precedemment collee, sans toucher a la mise en forme."""
    ligne, colonne = coordinate_to_tuple(cellule)
    derniere = feuille.cells.last_cell.row
    feuille.range((ligne, colonne), (derniere, colonne + max(largeur, 1) - 1)).clear_contents()


# --------------------------------------------------------------------------
def _via_openpyxl(blocs, destination: Path) -> ResultatCollage:
    from openpyxl import load_workbook

    resultat = ResultatCollage(chemin=destination, moteur="openpyxl")
    classeur = load_workbook(destination)

    for onglet, donnees in blocs:
        if onglet.onglet not in classeur.sheetnames:
            resultat.avertissements.append(
                f"Onglet '{onglet.onglet}' absent du classeur "
                f"(present : {classeur.sheetnames})"
            )
            LOG.warning("%s", resultat.avertissements[-1])
            continue

        feuille = classeur[onglet.onglet]
        ligne_depart, colonne_depart = coordinate_to_tuple(onglet.cellule)
        largeur = max(donnees.shape[1], 1)

        if onglet.effacer_avant:
            for ligne in range(ligne_depart, max(feuille.max_row, ligne_depart) + 1):
                for colonne in range(colonne_depart, colonne_depart + largeur):
                    feuille.cell(row=ligne, column=colonne).value = None

        for decalage, valeurs in enumerate(_valeurs(donnees, onglet.avec_entetes)):
            for indice, valeur in enumerate(valeurs):
                cellule = feuille.cell(
                    row=ligne_depart + decalage, column=colonne_depart + indice, value=valeur
                )
                if isinstance(valeur, (dt.datetime, dt.date)):
                    cellule.number_format = style.FORMAT_DATE

        resultat.onglets.append(onglet.onglet)
        resultat.lignes += len(donnees)
        LOG.info("[%s] %d ligne(s) collees en %s", onglet.onglet, len(donnees), onglet.cellule)

    classeur.save(destination)
    return resultat


__all__ = ["ClasseurIndisponible", "ResultatCollage", "bloc", "remplir"]
