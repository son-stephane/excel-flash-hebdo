"""Journalisation : console lisible pour l'utilisateur, fichier detaille pour l'enquete."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONFIGURE = False


def configurer(dossier_logs: Path | None = None, verbeux: bool = False) -> None:
    """Installe les handlers. Idempotent : appelable plusieurs fois sans degat."""
    global _CONFIGURE
    if _CONFIGURE:
        return

    racine = logging.getLogger("flash")
    racine.setLevel(logging.DEBUG)
    racine.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbeux else logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    racine.addHandler(console)

    if dossier_logs is not None:
        dossier_logs.mkdir(parents=True, exist_ok=True)
        fichier = logging.FileHandler(dossier_logs / "flash.log", encoding="utf-8")
        fichier.setLevel(logging.DEBUG)
        fichier.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
        racine.addHandler(fichier)

    _CONFIGURE = True


def journal(nom: str) -> logging.Logger:
    return logging.getLogger(f"flash.{nom}")
