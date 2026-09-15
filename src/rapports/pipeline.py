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
from .sorties import classeur_existant, excel, graphique, html

LOG = journal("pipeline")


@dataclass
class Sortie:
    rapport: Rapport
    semaine: str
    resultat: calculs.Resultat
    classeur: Path
    page_html: Path
    image: Path | None
    collage: classeur_existant.ResultatCollage | None = None

    def resume(self) -> str:
        lignes = [
            f"{self.rapport.libelle} - semaine {self.semaine}",
            f"  {self.resultat.resume()}",
            f"  Excel : {self.classeur}",
            f"  HTML  : {self.page_html}",
        ]
        if self.collage is not None:
            lignes.append(f"  Ancien classeur : {self.collage.chemin}")
            lignes.append(f"    {self.collage.resume()}")
            for message in self.collage.avertissements:
                lignes.append(f"  [!] {message}")
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

    collage = _remplir_classeur_existant(cfg, rapport, resultat, semaine)

    return Sortie(
        rapport=rapport, semaine=semaine, resultat=resultat,
        classeur=classeur, page_html=page, image=image, collage=collage,
    )


def _remplir_classeur_existant(
    cfg: Config, rapport: Rapport, resultat: calculs.Resultat, semaine: str
) -> classeur_existant.ResultatCollage | None:
    """Alimente le rapport historique, tant qu'il vit en parallele des nouveaux."""
    reglages = cfg.classeur_existant
    if reglages is None or not reglages.actif:
        return None

    onglets = reglages.pour_rapport(rapport.nom)
    if not onglets:
        return None

    destination = (
        cfg.dossier_sorties / semaine / f"{cfg.modele_classeur.stem}_{semaine}.xlsx"
    )
    try:
        return classeur_existant.remplir(
            {rapport.nom: resultat}, onglets, cfg.modele_classeur, destination,
            moteur=reglages.moteur,
        )
    except classeur_existant.ClasseurIndisponible as exc:
        LOG.warning("Ancien classeur non produit : %s", exc)
        return None
