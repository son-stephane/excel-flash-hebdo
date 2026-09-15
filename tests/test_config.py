"""La configuration doit echouer au chargement, avec un message actionnable."""

import pytest

from rapports.config import ConfigurationInvalide, charger


def test_chargement_nominal(cfg):
    assert cfg.noms == ["activite"]
    rapport = cfg.rapport("activite")
    assert rapport.colonne_date == "Date CAV"
    assert rapport.colonne_dr == "Code DR"
    assert rapport.segments == ("Grand Public", "Pro")
    assert rapport.dr_exclue == "DR99"


def test_rapport_inconnu(cfg):
    with pytest.raises(ConfigurationInvalide, match="Rapport inconnu"):
        cfg.rapport("inexistant")


def test_role_de_colonne_manquant(projet):
    fichier = projet / "config" / "rapports.toml"
    fichier.write_text(
        fichier.read_text(encoding="utf-8").replace('dr = "Code DR"\n\n[rapports.objectifs', '\n[rapports.objectifs'),
        encoding="utf-8",
    )
    with pytest.raises(ConfigurationInvalide) as erreur:
        charger(projet)
    assert "colonnes" in str(erreur.value)
    assert "'dr'" in str(erreur.value)


def test_deux_rapports_de_meme_nom(projet):
    fichier = projet / "config" / "rapports.toml"
    contenu = fichier.read_text(encoding="utf-8")
    fichier.write_text(contenu + contenu.split("[general]")[0] + contenu[contenu.index("[[rapports]]"):], encoding="utf-8")
    with pytest.raises(ConfigurationInvalide, match="meme nom|portent le nom"):
        charger(projet)


def test_surcharge_locale(projet):
    (projet / "config" / "config.local.toml").write_text(
        '[general]\ndossier_sorties = "ailleurs"\n', encoding="utf-8"
    )
    cfg = charger(projet)
    assert cfg.dossier_sorties.name == "ailleurs"
    # la surcharge ne remplace que ce qu'elle mentionne
    assert cfg.dossier_entrees.name == "entrees"
