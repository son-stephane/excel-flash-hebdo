"""Lecture et validation de config/rapports.toml.

Toute la description d'un rapport est declarative : noms de colonnes, filtres,
totaux. Ajouter un rapport ne demande donc aucune ligne de code.

La validation est volontairement stricte et effectuee au chargement : une
configuration incoherente doit echouer immediatement, avec un message qui dit
quoi corriger, plutot qu'a mi-parcours du traitement.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RACINE_PROJET = Path(__file__).resolve().parents[2]

ROLES_SOURCE = ("date", "segment", "dr")
ROLES_OBJECTIFS = ("dr", "debut_annee", "annuel")
CONTENUS = ("donnees", "objectifs", "synthese")


class ConfigurationInvalide(RuntimeError):
    pass


@dataclass(frozen=True)
class Rapport:
    nom: str
    libelle: str
    unite: str
    fichier: str
    onglet: int | str
    objectifs_fichier: str
    objectifs_onglet: int | str
    colonnes: dict[str, str]
    objectifs_colonnes: dict[str, str]
    segments: tuple[str, ...]
    dr_exclue: str | None

    @property
    def colonne_date(self) -> str:
        return self.colonnes["date"]

    @property
    def colonne_segment(self) -> str:
        return self.colonnes["segment"]

    @property
    def colonne_dr(self) -> str:
        return self.colonnes["dr"]


@dataclass(frozen=True)
class OngletCollage:
    """Un onglet du classeur existant, et ce que l'on y colle."""

    onglet: str
    contenu: str
    rapport: str
    cellule: str = "A2"
    avec_entetes: bool = False
    effacer_avant: bool = True


MOTEURS = ("auto", "excel", "openpyxl")


@dataclass(frozen=True)
class ClasseurExistant:
    actif: bool
    modele: str
    moteur: str
    onglets: tuple[OngletCollage, ...]

    def pour_rapport(self, nom: str) -> tuple[OngletCollage, ...]:
        return tuple(o for o in self.onglets if o.rapport == nom)


@dataclass
class Config:
    general: dict[str, Any]
    rapports: dict[str, Rapport]
    racine: Path
    classeur_existant: ClasseurExistant | None = None

    @property
    def modele_classeur(self) -> Path:
        if self.classeur_existant is None:
            raise ConfigurationInvalide("Aucun classeur existant configure")
        chemin = Path(self.classeur_existant.modele).expanduser()
        return chemin if chemin.is_absolute() else (self.racine / chemin)

    @property
    def noms(self) -> list[str]:
        return list(self.rapports)

    def rapport(self, nom: str) -> Rapport:
        try:
            return self.rapports[nom]
        except KeyError:
            raise ConfigurationInvalide(
                f"Rapport inconnu : {nom!r}. Rapports configures : "
                f"{', '.join(self.noms) or '(aucun)'}"
            ) from None

    def chemin(self, cle: str) -> Path:
        valeur = Path(self.general[cle]).expanduser()
        return valeur if valeur.is_absolute() else (self.racine / valeur)

    @property
    def dossier_entrees(self) -> Path:
        return self.chemin("dossier_entrees")

    @property
    def dossier_sorties(self) -> Path:
        return self.chemin("dossier_sorties")


def _lire(chemin: Path) -> dict[str, Any]:
    with chemin.open("rb") as flux:
        return tomllib.load(flux)


def _fusionner(base: dict, surcharge: dict) -> dict:
    """Fusion recursive : la surcharge ne remplace que ce qu'elle mentionne."""
    resultat = dict(base)
    for cle, valeur in surcharge.items():
        if isinstance(valeur, dict) and isinstance(resultat.get(cle), dict):
            resultat[cle] = _fusionner(resultat[cle], valeur)
        else:
            resultat[cle] = valeur
    return resultat


def _construire_rapport(brut: dict[str, Any], rang: int) -> Rapport:
    ou = f"rapports[{rang}]"
    try:
        nom = brut["nom"]
    except KeyError:
        raise ConfigurationInvalide(f"{ou} : champ obligatoire 'nom' manquant") from None

    ou = f"rapport '{nom}'"
    for champ in ("fichier", "objectifs_fichier"):
        if champ not in brut:
            raise ConfigurationInvalide(f"{ou} : champ obligatoire '{champ}' manquant")

    colonnes = brut.get("colonnes", {})
    objectifs_colonnes = brut.get("objectifs_colonnes", {})

    for roles, table, nom_table in (
        (ROLES_SOURCE, colonnes, "colonnes"),
        (ROLES_OBJECTIFS, objectifs_colonnes, "objectifs_colonnes"),
    ):
        absents = [r for r in roles if not table.get(r)]
        if absents:
            raise ConfigurationInvalide(
                f"{ou} : [rapports.{nom_table}] doit definir {list(roles)}.\n"
                f"  Manquant : {absents}\n"
                f"  A gauche le role attendu par le script, a droite l'en-tete "
                f"exact de ton fichier."
            )

    exclue = (brut.get("totaux", {}).get("dr_exclue") or "").strip()

    return Rapport(
        nom=nom,
        libelle=brut.get("libelle", nom),
        unite=brut.get("unite", "lignes"),
        fichier=brut["fichier"],
        onglet=brut.get("onglet", 0),
        objectifs_fichier=brut["objectifs_fichier"],
        objectifs_onglet=brut.get("objectifs_onglet", 0),
        colonnes=dict(colonnes),
        objectifs_colonnes=dict(objectifs_colonnes),
        segments=tuple(brut.get("filtres", {}).get("segments", ())),
        dr_exclue=exclue or None,
    )


def _construire_classeur(brut: dict[str, Any], noms_rapports: set[str]) -> ClasseurExistant | None:
    if not brut:
        return None

    onglets = []
    for rang, entree in enumerate(brut.get("onglets", [])):
        ou = f"classeur_existant.onglets[{rang}]"
        for champ in ("onglet", "contenu", "rapport"):
            if not entree.get(champ):
                raise ConfigurationInvalide(f"{ou} : champ obligatoire '{champ}' manquant")
        if entree["contenu"] not in CONTENUS:
            raise ConfigurationInvalide(
                f"{ou} : contenu {entree['contenu']!r} inconnu. "
                f"Valeurs possibles : {list(CONTENUS)}"
            )
        if entree["rapport"] not in noms_rapports:
            raise ConfigurationInvalide(
                f"{ou} : rapport {entree['rapport']!r} inconnu. "
                f"Rapports configures : {sorted(noms_rapports)}"
            )
        onglets.append(
            OngletCollage(
                onglet=entree["onglet"],
                contenu=entree["contenu"],
                rapport=entree["rapport"],
                cellule=entree.get("cellule", "A2"),
                avec_entetes=bool(entree.get("avec_entetes", False)),
                effacer_avant=bool(entree.get("effacer_avant", True)),
            )
        )

    doublons = [o.onglet for o in onglets if [x.onglet for x in onglets].count(o.onglet) > 1]
    if doublons:
        raise ConfigurationInvalide(
            f"classeur_existant : plusieurs blocs visent le meme onglet {sorted(set(doublons))}"
        )

    moteur = brut.get("moteur", "auto")
    if moteur not in MOTEURS:
        raise ConfigurationInvalide(
            f"classeur_existant.moteur : {moteur!r} inconnu. Valeurs possibles : {list(MOTEURS)}"
        )

    return ClasseurExistant(
        actif=bool(brut.get("actif", True)),
        modele=brut.get("modele", "templates/classeur/rapport_existant.xlsx"),
        moteur=moteur,
        onglets=tuple(onglets),
    )


def charger(racine: Path | None = None) -> Config:
    racine = Path(racine or RACINE_PROJET).resolve()
    principal = racine / "config" / "rapports.toml"
    if not principal.exists():
        raise ConfigurationInvalide(f"Configuration introuvable : {principal}")

    reglages = _lire(principal)
    local = racine / "config" / "config.local.toml"
    if local.exists():
        reglages = _fusionner(reglages, _lire(local))

    rapports: dict[str, Rapport] = {}
    for rang, brut in enumerate(reglages.get("rapports", [])):
        rapport = _construire_rapport(brut, rang)
        if rapport.nom in rapports:
            raise ConfigurationInvalide(f"Deux rapports portent le nom {rapport.nom!r}")
        rapports[rapport.nom] = rapport

    if not rapports:
        raise ConfigurationInvalide(
            f"Aucun rapport configure dans {principal}. Ajouter un bloc [[rapports]]."
        )

    general = reglages.get("general", {})
    for cle in ("dossier_entrees", "dossier_sorties"):
        general.setdefault(cle, f"data/{cle.split('_')[1]}")

    classeur = _construire_classeur(reglages.get("classeur_existant", {}), set(rapports))

    return Config(
        general=general, rapports=rapports, racine=racine, classeur_existant=classeur
    )
