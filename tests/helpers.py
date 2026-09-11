"""Fabriques de donnees de test partagees par les modules de test."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd


def ecrire_export(dossier: Path, lignes: list[dict], nom: str = "ventes_export.csv") -> Path:
    """Ecrit un export au format attendu par le schema de test."""
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    pd.DataFrame(lignes).to_csv(chemin, sep=";", index=False, encoding="utf-8", decimal=",")
    return chemin


def ligne(identifiant: str, jour: dt.date, statut: str = "Ouvert", montant: str = "100,50") -> dict:
    return {
        "Id": identifiant,
        "Date": jour.strftime("%d/%m/%Y"),
        "Statut": statut,
        "Montant": montant,
    }
