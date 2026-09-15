"""Journalisation : messages lisibles en console, detail complet en fichier."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURE = False


def configurer(dossier: Path | None = None, verbeux: bool = False) -> None:
    global _CONFIGURE
    if _CONFIGURE:
        return

    racine = logging.getLogger("rapports")
    racine.setLevel(logging.DEBUG)
    racine.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbeux else logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    racine.addHandler(console)

    if dossier is not None:
        dossier.mkdir(parents=True, exist_ok=True)
        fichier = logging.FileHandler(dossier / "rapports.log", encoding="utf-8")
        fichier.setLevel(logging.DEBUG)
        fichier.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
        racine.addHandler(fichier)

    _CONFIGURE = True


def journal(nom: str) -> logging.Logger:
    return logging.getLogger(f"rapports.{nom}")
