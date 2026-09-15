"""Mini-projet isole dans un dossier temporaire."""

from __future__ import annotations

from pathlib import Path

import pytest

from rapports.config import charger

CONFIG = """
[general]
dossier_entrees = "entrees"
dossier_sorties = "sorties"

[[rapports]]
nom = "activite"
libelle = "Activite de test"
unite = "dossiers"
fichier = "*activite*.xlsx"
objectifs_fichier = "*objectifs*.xlsx"

[rapports.colonnes]
date = "Date CAV"
segment = "Segment"
dr = "Code DR"

[rapports.objectifs_colonnes]
dr = "Code DR"
debut_annee = "Objectif debut annee"
annuel = "Objectif annuel"

[rapports.filtres]
segments = ["Grand Public", "Pro"]

[rapports.totaux]
dr_exclue = "DR99"
"""


@pytest.fixture
def projet(tmp_path: Path) -> Path:
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "rapports.toml").write_text(CONFIG, encoding="utf-8")
    (tmp_path / "entrees").mkdir()
    (tmp_path / "templates").mkdir()
    return tmp_path


@pytest.fixture
def cfg(projet: Path):
    return charger(projet)


@pytest.fixture
def rapport(cfg):
    return cfg.rapport("activite")
