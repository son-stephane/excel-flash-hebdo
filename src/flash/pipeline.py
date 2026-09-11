"""Orchestration de bout en bout.

Une seule fonction fait foi, appelee aussi bien par la ligne de commande que
par l'interface Streamlit ou une tache planifiee. C'est ce qui permettra de
passer du mode assiste au mode 100% automatique sans rien reecrire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .extract import portail
from .ingest import snapshots
from .logging_setup import journal
from .paths import Emplacements
from .publish import charts, excel, mail
from .quality.checks import RapportControles, controler
from .transform import marts
from .weeks import semaine_courante, valider

LOG = journal("pipeline")


@dataclass
class Resultat:
    semaine: str
    etapes: list[str] = field(default_factory=list)
    ingestions: list[snapshots.ResultatIngestion] = field(default_factory=list)
    controles: RapportControles | None = None
    lignes_mart: int = 0
    graphiques: list[Path] = field(default_factory=list)
    classeur: Path | None = None
    mail: mail.ResultatMail | None = None
    arrete_par_controles: bool = False

    def resume(self) -> str:
        lignes = [f"Flash {self.semaine} : {' > '.join(self.etapes) or 'aucune etape'}"]
        for ingestion in self.ingestions:
            lignes.append(
                f"  {ingestion.rapport:<12} {ingestion.lignes_conservees:>7} lignes "
                f"({ingestion.lignes_filtrees} filtrees)"
            )
        if self.controles:
            lignes.append(f"  controles    {self.controles.resume()}")
        if self.lignes_mart:
            lignes.append(f"  mart         {self.lignes_mart} lignes agregees")
        if self.graphiques:
            lignes.append(f"  graphiques   {len(self.graphiques)} fichier(s)")
        if self.classeur:
            lignes.append(f"  classeur     {self.classeur}")
        if self.mail:
            lignes.append(f"  mail         {self.mail.resume()}")
        if self.arrete_par_controles:
            lignes.append("  >> ARRETE par les controles qualite : rien n'a ete diffuse.")
        return "\n".join(lignes)


def executer(
    cfg: Config,
    semaine: str | None = None,
    *,
    extraire: bool = True,
    diffuser: bool = True,
    avec_excel: bool = True,
    forcer: bool = False,
    rapports: list[str] | None = None,
) -> Resultat:
    semaine = valider(semaine or semaine_courante())
    Emplacements(cfg).initialiser()
    resultat = Resultat(semaine=semaine)

    # 1. Extraction -------------------------------------------------------
    if extraire:
        try:
            portail.telecharger_tout(cfg, semaine, rapports)
            resultat.etapes.append("extraction")
        except portail.EchecTelechargement as exc:
            LOG.warning("%s", exc)
            LOG.warning(
                "Poursuite avec les fichiers deja presents (00_raw ou inbox). "
                "Utiliser --sans-extraction pour ne plus tenter le telechargement."
            )

    # 2. Ingestion --------------------------------------------------------
    for nom in rapports or cfg.rapports:
        resultat.ingestions.append(snapshots.ingerer(cfg, nom, semaine))
    resultat.etapes.append("ingestion")

    # 3. Controles qualite ------------------------------------------------
    resultat.controles = controler(cfg, semaine, rapports)
    resultat.controles.ecrire(cfg)
    resultat.etapes.append("controles")

    for controle in resultat.controles.controles:
        if controle.niveau != "OK":
            LOG.warning("%s", controle)

    if resultat.controles.bloquant and not forcer:
        resultat.arrete_par_controles = True
        LOG.error(
            "%d controle(s) bloquant(s) : le flash n'est pas publie.",
            len(resultat.controles.echecs),
        )
        mail.alerter(cfg, semaine, resultat.controles)
        return resultat
    if resultat.controles.bloquant and forcer:
        LOG.warning("Controles bloquants ignores (--forcer) : publication sous reserve.")

    # 4. Mart -------------------------------------------------------------
    resultat.lignes_mart = len(marts.construire(cfg, semaine))
    resultat.etapes.append("mart")

    # 5. Publication ------------------------------------------------------
    moteur = cfg.bloc("publication").get("moteur_graphiques", "python")
    if moteur == "excel" and avec_excel:
        sortie = excel.publier(cfg, semaine, avec_excel=True)
        resultat.classeur = sortie.classeur
        resultat.graphiques = sortie.graphiques
    else:
        if avec_excel:
            try:
                sortie = excel.publier(cfg, semaine, avec_excel=False)
                resultat.classeur = sortie.classeur
            except excel.TemplateInvalide as exc:
                LOG.warning("Classeur non produit : %s", exc)
        resultat.graphiques = charts.produire(cfg, semaine)
    resultat.etapes.append("publication")

    # 6. Diffusion --------------------------------------------------------
    if diffuser:
        resultat.mail = mail.preparer(
            cfg, semaine, resultat.graphiques,
            controles=resultat.controles, classeur=resultat.classeur,
        )
        resultat.etapes.append("diffusion")

    return resultat
