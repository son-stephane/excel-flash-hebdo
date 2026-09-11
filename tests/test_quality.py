"""Controles qualite et detection des corrections retroactives.

Ces deux mecanismes repondent a la meme question : quand un chiffre parait
faux, vient-il du traitement ou de la source ?
"""

import datetime as dt

from flash.ingest import snapshots
from flash.paths import Emplacements
from flash.quality import checks, diff
from helpers import ecrire_export, ligne

PASSE = dt.date(2026, 3, 12)
SEMAINE_1, SEMAINE_2 = "2026-W36", "2026-W37"


def _ingerer(cfg, semaine, lignes):
    ecrire_export(Emplacements(cfg).raw(semaine), lignes)
    return snapshots.ingerer(cfg, "ventes", semaine)


def test_diff_detecte_une_correction_retroactive(cfg):
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE, "Ouvert", "100,00"), ligne("L2", PASSE)])
    # La source corrige L1 et ajoute L3 : exactement ce que fait le portail.
    _ingerer(
        cfg, SEMAINE_2,
        [ligne("L1", PASSE, "Clos", "180,00"), ligne("L2", PASSE), ligne("L3", PASSE)],
    )

    resultat = diff.comparer(cfg, "ventes", SEMAINE_2)

    assert resultat.semaine_precedente == SEMAINE_1
    assert resultat.compter(diff.MODIFIEE) == 1
    assert resultat.compter(diff.AJOUTEE) == 1
    assert resultat.compter(diff.SUPPRIMEE) == 0
    # La ligne modifiee porte sur mars : elle a deja ete publiee.
    assert resultat.retroactifs == 1


def test_premiere_semaine_sans_comparaison(cfg):
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE)])
    resultat = diff.comparer(cfg, "ventes", SEMAINE_1)
    assert not resultat.disponible
    assert resultat.retroactifs == 0


def test_volumetrie_hors_bornes_est_bloquante(cfg):
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE)])  # 1 ligne, minimum attendu 2

    rapport = checks.controler(cfg, SEMAINE_1)

    assert rapport.bloquant
    noms = {c.nom for c in rapport.echecs}
    assert "volumetrie_absolue" in noms


def test_doublon_de_cle_bloquant(cfg):
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE), ligne("L1", PASSE), ligne("L2", PASSE)])

    rapport = checks.controler(cfg, SEMAINE_1)

    assert rapport.bloquant
    assert any(c.nom == "unicite_cle" for c in rapport.echecs)


def test_modalite_inattendue_alerte_sans_bloquer(cfg):
    # "En attente" n'est pas dans controles.valeurs_autorisees
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE), ligne("L2", PASSE, "En attente")])

    rapport = checks.controler(cfg, SEMAINE_1)

    assert not rapport.bloquant
    alertes = {c.nom for c in rapport.alertes}
    assert "valeurs_autorisees" in alertes


def test_variation_de_volumetrie_bloquante(cfg):
    _ingerer(cfg, SEMAINE_1, [ligne(f"L{i}", PASSE) for i in range(10)])
    _ingerer(cfg, SEMAINE_2, [ligne(f"L{i}", PASSE) for i in range(3)])  # -70%

    rapport = checks.controler(cfg, SEMAINE_2)

    assert rapport.bloquant
    assert any(c.nom == "variation_volumetrie" for c in rapport.echecs)


def test_rapport_serialisable(cfg, tmp_path):
    _ingerer(cfg, SEMAINE_1, [ligne("L1", PASSE), ligne("L2", PASSE)])
    rapport = checks.controler(cfg, SEMAINE_1)
    rapport.ecrire(cfg)

    chemin = Emplacements(cfg).rapport_qualite(SEMAINE_1)
    assert chemin.exists()
    assert '"semaine": "2026-W36"' in chemin.read_text(encoding="utf-8")
