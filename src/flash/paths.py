"""Organisation physique des donnees.

    data/
      inbox/                                  depot manuel (mode degrade)
      00_raw/<semaine>/                       fichiers telecharges, jamais retouches
      10_snapshots/<rapport>/semaine=<s>/     snapshot fige, typE, en Parquet
      20_diff/<rapport>/semaine=<s>/          changements vs semaine precedente
      30_mart/semaine=<s>/                    table agregee prete a publier
      90_sorties/<semaine>/                   PNG, classeur, mail, rapport qualite
      _logs/

Regle : un fichier Parquet est ecrit une fois et n'est plus jamais modifie.
C'est ce qui rend le stockage compatible avec une synchro SharePoint/OneDrive
(des fichiers qui s'ajoutent, jamais un gros fichier reecrit en permanence).
Rejouer une semaine remplace son dossier de partition, ce qui garde le
traitement idempotent : relancer deux fois ne duplique rien.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config

NOM_PARQUET = "data.parquet"


class Emplacements:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.racine = cfg.chemin("racine_donnees")

    # -- entree ------------------------------------------------------------
    @property
    def inbox(self) -> Path:
        return self.cfg.chemin("inbox")

    def raw(self, semaine: str) -> Path:
        return self.racine / "00_raw" / semaine

    # -- historique --------------------------------------------------------
    def snapshot(self, rapport: str, semaine: str) -> Path:
        return self.racine / "10_snapshots" / rapport / f"semaine={semaine}" / NOM_PARQUET

    def snapshots_glob(self, rapport: str) -> str:
        return str(self.racine / "10_snapshots" / rapport / "semaine=*" / NOM_PARQUET)

    def semaines_disponibles(self, rapport: str) -> list[str]:
        """Semaines deja historisees pour ce rapport, triees chronologiquement."""
        dossier = self.racine / "10_snapshots" / rapport
        if not dossier.exists():
            return []
        return sorted(
            p.name.split("=", 1)[1]
            for p in dossier.iterdir()
            if p.is_dir() and p.name.startswith("semaine=") and (p / NOM_PARQUET).exists()
        )

    # -- derives -----------------------------------------------------------
    def diff(self, rapport: str, semaine: str) -> Path:
        return self.racine / "20_diff" / rapport / f"semaine={semaine}" / NOM_PARQUET

    def mart(self, semaine: str) -> Path:
        return self.racine / "30_mart" / f"semaine={semaine}" / NOM_PARQUET

    def mart_glob(self) -> str:
        return str(self.racine / "30_mart" / "semaine=*" / NOM_PARQUET)

    # -- sorties -----------------------------------------------------------
    def sorties(self, semaine: str) -> Path:
        return self.cfg.chemin("sorties") / semaine

    def graphiques(self, semaine: str) -> Path:
        return self.sorties(semaine) / "graphiques"

    def classeur(self, semaine: str) -> Path:
        return self.sorties(semaine) / f"flash_hebdo_{semaine}.xlsx"

    def rapport_qualite(self, semaine: str) -> Path:
        return self.sorties(semaine) / "controles_qualite.json"

    def logs(self) -> Path:
        return self.racine / "_logs"

    def template_excel(self) -> Path:
        return self.cfg.chemin("template_excel")

    # -- utilitaires -------------------------------------------------------
    @staticmethod
    def preparer(chemin: Path) -> Path:
        """Cree le dossier parent et retourne le chemin."""
        chemin.parent.mkdir(parents=True, exist_ok=True)
        return chemin

    def initialiser(self) -> None:
        for dossier in (
            self.inbox,
            self.racine / "00_raw",
            self.racine / "10_snapshots",
            self.racine / "20_diff",
            self.racine / "30_mart",
            self.cfg.chemin("sorties"),
            self.logs(),
        ):
            dossier.mkdir(parents=True, exist_ok=True)
