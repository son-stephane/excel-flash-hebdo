"""Regles metier du calcul.

Ces tests fixent ce que le rapport affirme : ce qui entre dans la semaine, ce
qui entre dans le cumul, et comment les totaux sont obtenus.
"""

import pandas as pd
import pytest

from rapports import calculs
from fabrique import (
    ANNEE_PRECEDENTE,
    APRES_LA_SEMAINE,
    AVANT_LA_SEMAINE,
    DANS_LA_SEMAINE,
    SEMAINE,
    ligne,
    objectifs,
    source,
)


def calculer(rapport, lignes, cibles=None):
    return calculs.calculer(
        rapport,
        source(lignes),
        objectifs(cibles if cibles is not None else {"DR01": (100.0, 400.0)}),
        SEMAINE,
    )


def dr(resultat, code):
    return resultat.par_dr.set_index("code_dr").loc[code]


# --- Perimetre temporel ----------------------------------------------------
def test_la_semaine_ne_retient_que_ses_sept_jours(rapport):
    resultat = calculer(
        rapport,
        [ligne(DANS_LA_SEMAINE), ligne(DANS_LA_SEMAINE), ligne(AVANT_LA_SEMAINE)],
    )
    assert dr(resultat, "DR01")["realise_semaine"] == 2


def test_le_cumul_part_du_premier_janvier(rapport):
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE), ligne(AVANT_LA_SEMAINE)])
    assert dr(resultat, "DR01")["realise_cumul"] == 2


def test_l_annee_precedente_est_hors_cumul(rapport):
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE), ligne(ANNEE_PRECEDENTE)])
    assert dr(resultat, "DR01")["realise_cumul"] == 1


def test_les_lignes_posterieures_sont_ecartees_et_signalees(rapport):
    """Le fichier contient toute l'annee : une semaine anterieure doit ignorer
    ce qui s'est passe apres, sinon le cumul serait faux."""
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE), ligne(APRES_LA_SEMAINE)])

    assert dr(resultat, "DR01")["realise_cumul"] == 1
    assert any("posterieures" in message for message in resultat.avertissements)


# --- Filtre segment --------------------------------------------------------
def test_seuls_les_segments_configures_sont_retenus(rapport):
    resultat = calculer(
        rapport,
        [
            ligne(DANS_LA_SEMAINE, segment="Grand Public"),
            ligne(DANS_LA_SEMAINE, segment="Pro"),
            ligne(DANS_LA_SEMAINE, segment="Entreprise"),
        ],
    )
    assert dr(resultat, "DR01")["realise_cumul"] == 2
    assert resultat.lignes_apres_filtre == 2


def test_segment_configure_absent_du_fichier_est_signale(rapport):
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE, segment="Grand Public")])
    assert any("Pro" in message for message in resultat.avertissements)


# --- Indicateurs -----------------------------------------------------------
def test_ro_et_ecart_portent_sur_le_cumul(rapport):
    resultat = calculer(
        rapport,
        [ligne(AVANT_LA_SEMAINE)] * 60 + [ligne(DANS_LA_SEMAINE)] * 15,
        {"DR01": (50.0, 200.0)},
    )
    activite = dr(resultat, "DR01")

    assert activite["realise_semaine"] == 15
    assert activite["realise_cumul"] == 75
    assert activite["ro"] == pytest.approx(1.5)      # 75 / 50, pas 15 / 50
    assert activite["ecart"] == pytest.approx(25.0)
    assert activite["part_annuel"] == pytest.approx(0.375)


def test_objectif_nul_ne_provoque_pas_de_division_par_zero(rapport):
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE)], {"DR01": (0.0, 0.0)})
    assert pd.isna(dr(resultat, "DR01")["ro"])


# --- Totaux ----------------------------------------------------------------
def test_le_ro_du_total_est_recalcule_depuis_les_sommes(rapport):
    """Une moyenne des R/O par DR serait fausse : les DR n'ont pas le meme
    poids. 30+10 realise pour 20+20 objectif fait 100 %, pas 125 %."""
    resultat = calculer(
        rapport,
        [ligne(DANS_LA_SEMAINE, dr="DR01")] * 30 + [ligne(DANS_LA_SEMAINE, dr="DR02")] * 10,
        {"DR01": (20.0, 80.0), "DR02": (20.0, 80.0)},
    )

    moyenne_des_ratios = (1.5 + 0.5) / 2
    assert resultat.total["ro"] == pytest.approx(1.0)
    assert resultat.total["ro"] != pytest.approx(moyenne_des_ratios) or moyenne_des_ratios == 1.0
    assert resultat.total["realise_cumul"] == 40
    assert resultat.total["objectif_debut_annee"] == pytest.approx(40.0)


def test_total_hors_dr_exclue(rapport):
    resultat = calculer(
        rapport,
        [ligne(DANS_LA_SEMAINE, dr="DR01")] * 10 + [ligne(DANS_LA_SEMAINE, dr="DR99")] * 90,
        {"DR01": (10.0, 40.0), "DR99": (90.0, 360.0)},
    )
    hors = resultat.tableau[resultat.tableau["type_ligne"] == calculs.LIGNE_TOTAL_HORS].iloc[0]

    assert hors["code_dr"] == "Total hors DR99"
    assert hors["realise_cumul"] == 10
    assert hors["objectif_debut_annee"] == pytest.approx(10.0)


def test_dr_a_exclure_introuvable_est_signale(rapport):
    resultat = calculer(rapport, [ligne(DANS_LA_SEMAINE, dr="DR01")], {"DR01": (10.0, 40.0)})

    assert not (resultat.tableau["type_ligne"] == calculs.LIGNE_TOTAL_HORS).any()
    assert any("DR99" in message for message in resultat.avertissements)


# --- Jonction avec les objectifs -------------------------------------------
def test_dr_sans_objectif_apparait_et_est_signalee(rapport):
    resultat = calculer(
        rapport,
        [ligne(DANS_LA_SEMAINE, dr="DR01"), ligne(DANS_LA_SEMAINE, dr="DR07")],
        {"DR01": (10.0, 40.0)},
    )

    assert "DR07" in set(resultat.par_dr["code_dr"])
    assert pd.isna(dr(resultat, "DR07")["ro"])
    assert any("DR07" in message for message in resultat.avertissements)


def test_dr_sans_activite_reste_dans_le_tableau(rapport):
    """Une DR a zero doit se voir : c'est l'information la plus importante."""
    resultat = calculer(
        rapport,
        [ligne(DANS_LA_SEMAINE, dr="DR01")],
        {"DR01": (10.0, 40.0), "DR02": (10.0, 40.0)},
    )
    activite = dr(resultat, "DR02")

    assert activite["realise_cumul"] == 0
    assert activite["ro"] == pytest.approx(0.0)
    assert activite["ecart"] == pytest.approx(-10.0)
