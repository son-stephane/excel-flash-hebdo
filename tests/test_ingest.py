"""L'ingestion doit refuser un fichier dont la structure a change : c'est le
mecanisme qui detecte qu'une requete du portail a ete modifiee en amont.
"""

import datetime as dt

import pandas as pd
import pytest

from flash.ingest import snapshots
from flash.paths import Emplacements

from helpers import ecrire_export, ligne

JOUR = dt.date(2026, 9, 8)


def test_typage_filtrage_et_metadonnees(cfg):
    ecrire_export(
        Emplacements(cfg).raw("2026-W37"),
        [
            ligne("L1", JOUR, "Ouvert", "1 234,50"),
            ligne("L2", JOUR, "Clos", "10,00"),
            ligne("L3", JOUR, "Annule", "99,00"),
        ],
    )

    resultat = snapshots.ingerer(cfg, "ventes", "2026-W37")

    assert resultat.lignes_lues == 3
    assert resultat.lignes_conservees == 2  # la ligne "Annule" est ecartee par le filtre

    donnees = snapshots.lire_snapshot(cfg, "ventes", "2026-W37")
    assert donnees["montant"].tolist() == [1234.50, 10.0]  # separateur de milliers absorbe
    assert donnees["date_operation"].iloc[0] == JOUR
    assert donnees[snapshots.COL_SEMAINE].unique().tolist() == ["2026-W37"]
    assert donnees[snapshots.COL_HASH].nunique() == 2


def test_refus_si_colonne_manquante(cfg):
    dossier = Emplacements(cfg).raw("2026-W37")
    dossier.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"Id": "L1", "Date": "08/09/2026", "Statut": "Ouvert"}]).to_csv(
        dossier / "ventes_export.csv", sep=";", index=False
    )

    with pytest.raises(snapshots.SchemaInattendu, match="Montant"):
        snapshots.ingerer(cfg, "ventes", "2026-W37")


def test_fichier_absent_message_actionnable(cfg):
    with pytest.raises(snapshots.FichierIntrouvable, match=r"\*ventes\*"):
        snapshots.ingerer(cfg, "ventes", "2026-W37")


def test_relance_idempotente(cfg):
    ecrire_export(Emplacements(cfg).raw("2026-W37"), [ligne("L1", JOUR)])
    premier = snapshots.ingerer(cfg, "ventes", "2026-W37")
    second = snapshots.ingerer(cfg, "ventes", "2026-W37")

    assert premier.chemin_snapshot == second.chemin_snapshot
    assert len(snapshots.lire_snapshot(cfg, "ventes", "2026-W37")) == 1


def test_le_depot_manuel_est_archive_puis_retire_de_l_inbox(cfg):
    """Un fichier laisse dans l'inbox serait rejoue la semaine suivante."""
    source = ecrire_export(Emplacements(cfg).inbox, [ligne("L1", JOUR)])
    snapshots.ingerer(cfg, "ventes", "2026-W37")

    archives = list(Emplacements(cfg).raw("2026-W37").glob("ventes__*.csv"))
    assert len(archives) == 1        # le contenu est conserve dans l'archive
    assert not source.exists()       # mais plus dans l'inbox


def test_relance_n_empile_pas_les_archives(cfg):
    ecrire_export(Emplacements(cfg).raw("2026-W37"), [ligne("L1", JOUR)])
    for _ in range(3):
        snapshots.ingerer(cfg, "ventes", "2026-W37")

    assert len(list(Emplacements(cfg).raw("2026-W37").glob("*.csv"))) == 1


def test_xlsx_conserve_les_dates_typees(cfg, projet):
    """Une cellule date d'Excel n'est pas un texte : le format declare ne doit
    pas s'y appliquer, sinon toute la colonne est perdue silencieusement."""
    schema = projet / "config" / "schemas" / "ventes.toml"
    schema.write_text(
        schema.read_text(encoding="utf-8").replace('format = "csv"', 'format = "xlsx"'),
        encoding="utf-8",
    )
    from flash.config import charger

    cfg = charger(projet)

    dossier = Emplacements(cfg).inbox
    dossier.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"Id": ["L1", "L2"], "Date": [JOUR, JOUR], "Statut": ["Ouvert", "Clos"],
         "Montant": [1234.56, 10.0]}
    ).to_excel(dossier / "ventes_export.xlsx", index=False)

    snapshots.ingerer(cfg, "ventes", "2026-W37")
    donnees = snapshots.lire_snapshot(cfg, "ventes", "2026-W37")

    assert donnees["date_operation"].notna().all()
    assert donnees["date_operation"].iloc[0] == JOUR
    assert donnees["montant"].tolist() == [1234.56, 10.0]


def test_format_de_date_errone_est_refuse(cfg):
    """Un schema qui decrit mal le fichier doit echouer bruyamment, plutot que
    de produire un snapshot aux dates vides que personne ne remarquera."""
    ecrire_export(
        Emplacements(cfg).raw("2026-W37"),
        [{"Id": "L1", "Date": "2026-09-08", "Statut": "Ouvert", "Montant": "10,00"}],
    )

    with pytest.raises(snapshots.SchemaInattendu) as erreur:
        snapshots.ingerer(cfg, "ventes", "2026-W37")

    message = str(erreur.value)
    assert "date_operation" in message
    assert "format_date" in message      # le reglage en cause est nomme
    assert "'2026-09-08'" in message     # la valeur lue est montree
