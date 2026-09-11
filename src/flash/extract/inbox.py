"""Mode degrade : fichiers deposes a la main.

Le pipeline doit pouvoir tourner meme quand le portail refuse de se laisser
piloter (interface modifiee, MFA recalcitrant, indisponibilite). L'utilisateur
depose alors ses exports dans ``data/inbox/`` et relance le traitement.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..ingest.snapshots import FichierIntrouvable, trouver_fichier
from ..logging_setup import journal
from ..paths import Emplacements

LOG = journal("inbox")


@dataclass
class EtatDepot:
    rapport: str
    fichier: Path | None
    motif: str

    @property
    def present(self) -> bool:
        return self.fichier is not None

    def __str__(self) -> str:
        if self.present:
            taille = self.fichier.stat().st_size / 1e6
            return f"[ OK ] {self.rapport:<12} {self.fichier.name} ({taille:.1f} Mo)"
        return f"[ -- ] {self.rapport:<12} manquant (motif attendu : {self.motif})"


def etat(cfg: Config, semaine: str) -> list[EtatDepot]:
    """Dit, pour chaque rapport, si un fichier exploitable est disponible."""
    lieux = Emplacements(cfg)
    dossiers = [lieux.raw(semaine), lieux.inbox]
    resultats = []
    for nom in cfg.rapports:
        schema = cfg.schema(nom)
        try:
            fichier = trouver_fichier(dossiers, schema)
        except FichierIntrouvable:
            fichier = None
        resultats.append(EtatDepot(nom, fichier, schema.fichier.motif))
    return resultats


def complet(cfg: Config, semaine: str) -> bool:
    return all(e.present for e in etat(cfg, semaine))
