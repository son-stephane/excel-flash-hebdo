"""Fixtures : un mini-projet complet, isole, dans un dossier temporaire."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from flash.config import charger

SETTINGS = """
[chemins]
racine_donnees = "data"
inbox = "data/inbox"
template_excel = "templates/modele.xlsx"
sorties = "data/90_sorties"

[excel]
onglet_donnees = "DONNEES"
tableau_donnees = "tbl_donnees"

[mail]
objet = "Flash {semaine}"
destinataires = ["test@example.com"]
brouillon = true

[alertes]
destinataires = ["alerte@example.com"]

[publication]
moteur_graphiques = "python"
"""

SCHEMA = """
nom = "ventes"
libelle = "Ventes de test"

[fichier]
motif = "*ventes*"
format = "csv"
separateur = ";"
encodage = "utf-8"
decimal = ","
format_date = "%d/%m/%Y"

[cle]
colonnes = ["id_ligne"]
colonne_date = "date_operation"
colonnes_comparees = ["statut", "montant"]

[[colonnes]]
source = "Id"
cible = "id_ligne"
type = "string"
obligatoire = true

[[colonnes]]
source = "Date"
cible = "date_operation"
type = "date"
obligatoire = true

[[colonnes]]
source = "Statut"
cible = "statut"
type = "string"
obligatoire = true

[[colonnes]]
source = "Montant"
cible = "montant"
type = "float"
obligatoire = true

[filtre]
expression = "statut != 'Annule'"

[controles]
lignes_min = 2
lignes_max = 100
variation_lignes_max_pct = 50.0
variation_total_max_pct = 50.0
mesure_totale = "montant"
colonnes_non_nulles = ["id_ligne", "montant"]
unicite = ["id_ligne"]

[controles.valeurs_autorisees]
statut = ["Ouvert", "Clos"]
"""


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    (tmp_path / "config" / "schemas").mkdir(parents=True)
    (tmp_path / "config" / "settings.toml").write_text(SETTINGS, encoding="utf-8")
    (tmp_path / "config" / "schemas" / "ventes.toml").write_text(SCHEMA, encoding="utf-8")
    (tmp_path / "templates").mkdir()
    return tmp_path


@pytest.fixture
def cfg(projet: Path):
    return charger(projet)
