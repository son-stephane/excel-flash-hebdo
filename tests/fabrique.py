"""Fabriques de donnees de test."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

# 2026-W37 va du lundi 7 au dimanche 13 septembre 2026.
SEMAINE = "2026-W37"
DANS_LA_SEMAINE = dt.date(2026, 9, 9)
AVANT_LA_SEMAINE = dt.date(2026, 3, 12)
APRES_LA_SEMAINE = dt.date(2026, 9, 20)
ANNEE_PRECEDENTE = dt.date(2025, 11, 4)


def ligne(jour: dt.date, dr: str = "DR01", segment: str = "Grand Public") -> dict:
    return {"Date CAV": jour, "Code DR": dr, "Segment": segment}


def source(lignes: list[dict]) -> pd.DataFrame:
    donnees = pd.DataFrame(lignes)
    donnees["Date CAV"] = pd.to_datetime(donnees["Date CAV"])
    donnees["Code DR"] = donnees["Code DR"].astype("string")
    donnees["Segment"] = donnees["Segment"].astype("string")
    return donnees


def objectifs(valeurs: dict[str, tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "code_dr": pd.Series(list(valeurs), dtype="string"),
            "objectif_debut_annee": [v[0] for v in valeurs.values()],
            "objectif_annuel": [v[1] for v in valeurs.values()],
        }
    )


def ecrire_excel(dossier: Path, nom: str, donnees: pd.DataFrame) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / nom
    donnees.to_excel(chemin, index=False)
    return chemin
