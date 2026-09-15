import datetime as dt

import pytest

from rapports import semaines


def test_identifiant_iso_d_une_date():
    assert semaines.semaine_de(dt.date(2026, 9, 9)) == "2026-W37"


def test_bornes_lundi_dimanche():
    debut, fin = semaines.bornes("2026-W37")
    assert (debut, fin) == (dt.date(2026, 9, 7), dt.date(2026, 9, 13))
    assert debut.weekday() == 0


def test_debut_annee_suit_l_annee_du_lundi():
    assert semaines.debut_annee("2026-W37") == dt.date(2026, 1, 1)
    # Semaine a cheval : le lundi 29/12/2025 appartient a la semaine ISO 2026-W01
    assert semaines.lundi_de("2026-W01") == dt.date(2025, 12, 29)
    assert semaines.debut_annee("2026-W01") == dt.date(2025, 1, 1)


def test_format_invalide_rejete():
    for mauvais in ["2026-37", "W37", "", "2026-W99"]:
        with pytest.raises(semaines.SemaineInvalide):
            semaines.valider(mauvais)


def test_libelle_lisible():
    assert semaines.libelle("2026-W37") == "S37 - du 07/09 au 13/09/2026"
