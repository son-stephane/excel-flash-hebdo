import datetime as dt

import pytest

from flash import weeks


def test_semaine_iso_d_une_date():
    assert weeks.semaine_de(dt.date(2026, 9, 11)) == "2026-W37"


def test_bornes_lundi_dimanche():
    debut, fin = weeks.bornes("2026-W37")
    assert debut == dt.date(2026, 9, 7)
    assert fin == dt.date(2026, 9, 13)
    assert debut.weekday() == 0


def test_semaine_precedente_traverse_l_annee():
    assert weeks.semaine_precedente("2026-W01") == "2025-W52"


def test_format_invalide_rejete():
    for mauvais in ["2026-37", "W37", "", "2026-W99"]:
        with pytest.raises(weeks.SemaineInvalide):
            weeks.valider(mauvais)


def test_libelle_lisible():
    assert weeks.libelle("2026-W37") == "S37 (07/09 au 13/09/2026)"
