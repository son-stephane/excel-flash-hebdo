"""Le chargement de configuration doit echouer TOT et avec un message clair :
une incoherence detectee au demarrage coute infiniment moins cher qu'un flash
faux envoye a toute une liste de diffusion.
"""

import pytest

from flash.config import ConfigurationInvalide, charger


def test_chargement_nominal(cfg):
    assert cfg.rapports == ["ventes"]
    schema = cfg.schema("ventes")
    assert schema.mapping == {
        "Id": "id_ligne", "Date": "date_operation",
        "Statut": "statut", "Montant": "montant",
    }
    assert schema.colonnes_obligatoires == ("id_ligne", "date_operation", "statut", "montant")


def test_rapport_inconnu(cfg):
    with pytest.raises(ConfigurationInvalide, match="Rapport inconnu"):
        cfg.schema("inexistant")


def test_surcharge_locale(projet):
    (projet / "config" / "settings.local.toml").write_text(
        '[mail]\ndestinataires = ["reel@example.com"]\n', encoding="utf-8"
    )
    cfg = charger(projet)
    assert cfg.bloc("mail")["destinataires"] == ["reel@example.com"]
    # la surcharge ne remplace que ce qu'elle mentionne
    assert cfg.bloc("mail")["brouillon"] is True


def test_colonne_referencee_mais_absente(projet):
    schema = projet / "config" / "schemas" / "ventes.toml"
    schema.write_text(
        schema.read_text(encoding="utf-8").replace(
            'unicite = ["id_ligne"]', 'unicite = ["colonne_fantome"]'
        ),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationInvalide, match="colonnes absentes du schema"):
        charger(projet)


def test_type_non_supporte(projet):
    schema = projet / "config" / "schemas" / "ventes.toml"
    schema.write_text(
        schema.read_text(encoding="utf-8").replace('type = "float"', 'type = "decimal"'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationInvalide, match="type non supporte"):
        charger(projet)
