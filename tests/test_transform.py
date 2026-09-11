"""Vues DuckDB et remontee aux lignes sources."""

import datetime as dt

import pytest

from flash import drill
from flash.ingest import snapshots
from flash.paths import Emplacements
from flash.transform import marts
from helpers import ecrire_export, ligne

MARS = dt.date(2026, 3, 12)
AVRIL = dt.date(2026, 4, 2)


@pytest.fixture
def historise(cfg):
    for semaine, lignes in {
        "2026-W36": [ligne("L1", MARS, "Ouvert", "100,00"), ligne("L2", AVRIL)],
        "2026-W37": [ligne("L1", MARS, "Clos", "180,00"), ligne("L2", AVRIL), ligne("L3", AVRIL)],
    }.items():
        ecrire_export(Emplacements(cfg).raw(semaine), lignes)
        snapshots.ingerer(cfg, "ventes", semaine)
    return cfg


def test_vue_semaine_et_vue_historique(historise):
    cfg = historise
    courante = marts.requete_libre(cfg, "SELECT count(*) AS n FROM ventes", "2026-W37")
    complete = marts.requete_libre(cfg, "SELECT count(*) AS n FROM ventes_historique", "2026-W37")

    assert int(courante["n"].iloc[0]) == 3
    assert int(complete["n"].iloc[0]) == 5  # les deux snapshots empiles


def test_le_snapshot_precedent_reste_intact(historise):
    """Un snapshot est fige : la correction de la source ne le reecrit pas."""
    ancien = marts.requete_libre(
        historise,
        "SELECT montant FROM ventes_historique WHERE _semaine = '2026-W36' AND id_ligne = 'L1'",
    )
    assert float(ancien["montant"].iloc[0]) == 100.0


def test_detail_remonte_les_lignes_sources(historise):
    resultats = drill.detailler(historise, "2026-W37", "statut = 'Clos'")

    assert "ventes" in resultats
    assert resultats["ventes"]["id_ligne"].tolist() == ["L1"]


def test_alias_mois_utilisable_dans_le_filtre(historise):
    resultats = drill.detailler(historise, "2026-W37", "mois = '2026-04'")

    assert sorted(resultats["ventes"]["id_ligne"]) == ["L2", "L3"]


def test_alias_traduit_en_sql():
    assert drill._traduire("mois = '2026-04'").startswith("strftime(date_operation")
    # un nom de colonne contenant l'alias ne doit pas etre casse
    assert drill._traduire("mois_cloture = 1") == "mois_cloture = 1"


def test_export_du_detail(historise, tmp_path):
    resultats = drill.detailler(historise, "2026-W37", "statut = 'Clos'")
    chemin = drill.exporter(historise, "2026-W37", resultats, tmp_path / "detail.xlsx")
    assert chemin.exists()
