"""Lecture des fichiers : refuser tot, avec un message qui dit quoi corriger."""

import pandas as pd
import pytest

from rapports import sources
from fabrique import DANS_LA_SEMAINE, ecrire_excel


def test_fichier_absent_liste_ce_qui_est_present(cfg, rapport):
    ecrire_excel(cfg.dossier_entrees, "autre_chose.xlsx", pd.DataFrame({"a": [1]}))

    with pytest.raises(sources.FichierIntrouvable) as erreur:
        sources.trouver(cfg.dossier_entrees, rapport.fichier, "source")

    message = str(erreur.value)
    assert "*activite*.xlsx" in message
    assert "autre_chose.xlsx" in message


def test_fichiers_temporaires_excel_ignores(cfg, rapport):
    """Un classeur ouvert cree un ~$fichier.xlsx qui n'est pas lisible."""
    ecrire_excel(cfg.dossier_entrees, "activite.xlsx", pd.DataFrame({"a": [1]}))
    (cfg.dossier_entrees / "~$activite.xlsx").write_bytes(b"verrou")

    trouve = sources.trouver(cfg.dossier_entrees, rapport.fichier, "source")
    assert trouve.name == "activite.xlsx"


def test_colonne_manquante_nomme_le_role_et_les_colonnes_reelles(cfg, rapport):
    chemin = ecrire_excel(
        cfg.dossier_entrees, "activite.xlsx",
        pd.DataFrame({"Date CAV": [DANS_LA_SEMAINE], "Segment": ["Pro"]}),  # pas de Code DR
    )

    with pytest.raises(sources.ColonnesInattendues) as erreur:
        sources.lire_source(rapport, chemin)

    message = str(erreur.value)
    assert "'dr'" in message and "Code DR" in message
    assert "Date CAV" in message  # les colonnes reellement presentes sont listees


def test_colonne_de_date_qui_n_en_est_pas_une(cfg, rapport):
    chemin = ecrire_excel(
        cfg.dossier_entrees, "activite.xlsx",
        pd.DataFrame({"Date CAV": ["abc", "def"], "Segment": ["Pro"] * 2, "Code DR": ["DR01"] * 2}),
    )

    with pytest.raises(sources.ColonnesInattendues, match="date exploitable"):
        sources.lire_source(rapport, chemin)


def test_colonnes_supplementaires_ignorees(cfg, rapport):
    chemin = ecrire_excel(
        cfg.dossier_entrees, "activite.xlsx",
        pd.DataFrame(
            {
                "Date CAV": [DANS_LA_SEMAINE], "Segment": ["Pro"], "Code DR": ["DR01"],
                "Commentaire": ["peu importe"], "Reference": ["X1"],
            }
        ),
    )
    lues = sources.lire_source(rapport, chemin)
    assert list(lues.columns) == ["Date CAV", "Segment", "Code DR"]


def test_objectifs_en_double_refuses(cfg, rapport):
    chemin = ecrire_excel(
        cfg.dossier_entrees, "objectifs.xlsx",
        pd.DataFrame(
            {
                "Code DR": ["DR01", "DR01"],
                "Objectif debut annee": [10, 20],
                "Objectif annuel": [40, 80],
            }
        ),
    )
    with pytest.raises(sources.ColonnesInattendues, match="plusieurs lignes"):
        sources.lire_objectifs(rapport, chemin)
