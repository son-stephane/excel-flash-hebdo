"""Enchainement complet pour un rapport et une semaine.

    fichiers Excel -> filtres -> volumes par DR -> objectifs -> sorties

Une seule fonction fait foi, appelee aussi bien par la ligne de commande que
par un futur script de telechargement ou une tache planifiee.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import calculs, sources
from .config import Config, Rapport
from .journal import journal
from .semaines import valider
from .sorties import excel, graphique, html

LOG = journal("pipeline")


@dataclass
class Sortie:
    rapport: Rapport
    semaine: str
    resultat: calculs.Resultat
    classeur: Path
    page_html: Path
    image: Path | None

    def resume(self) -> str:
        lignes = [
            f"{self.rapport.libelle} - semaine {self.semaine}",
            f"  {self.resultat.resume()}",
            f"  Excel : {self.classeur}",
            f"  HTML  : {self.page_html}",
        ]
        for message in self.resultat.avertissements:
            lignes.append(f"  [!] {message}")
        return "\n".join(lignes)


def executer(cfg: Config, nom: str, semaine: str) -> Sortie:
    rapport = cfg.rapport(nom)
    semaine = valider(semaine)
    LOG.info("=== %s | semaine %s ===", rapport.libelle, semaine)

    entrees = cfg.dossier_entrees
    chemin_source = sources.trouver(entrees, rapport.fichier, "source")
    chemin_objectifs = sources.trouver(entrees, rapport.objectifs_fichier, "objectifs")

    donnees = sources.lire_source(rapport, chemin_source)
    objectifs = sources.lire_objectifs(rapport, chemin_objectifs)
    resultat = calculs.calculer(rapport, donnees, objectifs, semaine)

    dossier = cfg.dossier_sorties / semaine
    base = f"{rapport.nom}_{semaine}"

    image = graphique.produire(resultat, dossier / f"{base}.png")
    classeur = excel.produire(resultat, dossier / f"{base}.xlsx")
    page = html.produire(
        resultat,
        dossier / f"{base}.html",
        cfg.racine / "templates",
        image,
        {"source": chemin_source.name, "objectifs": chemin_objectifs.name},
    )

    return Sortie(
        rapport=rapport, semaine=semaine, resultat=resultat,
        classeur=classeur, page_html=page, image=image,
    )
