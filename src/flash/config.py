"""Chargement de la configuration et des schemas de rapports.

Deux fichiers sont lus, dans cet ordre :
  * ``config/settings.toml``        -- versionne, valeurs par defaut
  * ``config/settings.local.toml``  -- non versionne, surcharges du poste
    (chemin SharePoint reel, vrais destinataires, identifiant du portail...)

Les schemas de rapports vivent dans ``config/schemas/*.toml``. Un schema
decrit a la fois la structure attendue du fichier, le filtrage metier et les
controles qualite : tout ce qui est propre a un rapport est declaratif, et
seul le code reste generique.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RACINE_PROJET = Path(__file__).resolve().parents[2]

TYPES_SUPPORTES = {"string", "int", "float", "date", "bool"}


class ConfigurationInvalide(RuntimeError):
    """La configuration est incoherente : on s'arrete plutot que de deviner."""


# --------------------------------------------------------------------------
# Schema d'un rapport
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class Colonne:
    source: str
    cible: str
    type: str
    obligatoire: bool = False


@dataclass(frozen=True)
class FormatFichier:
    motif: str
    format: str = "csv"
    separateur: str = ";"
    encodage: str = "utf-8-sig"
    decimal: str = ","
    format_date: str | None = None


@dataclass(frozen=True)
class Cle:
    colonnes: tuple[str, ...]
    colonne_date: str
    colonnes_comparees: tuple[str, ...]


@dataclass(frozen=True)
class Controles:
    lignes_min: int = 0
    lignes_max: int = 10_000_000
    variation_lignes_max_pct: float = 100.0
    variation_total_max_pct: float = 100.0
    mesure_totale: str | None = None
    colonnes_non_nulles: tuple[str, ...] = ()
    unicite: tuple[str, ...] = ()
    valeurs_autorisees: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class SchemaRapport:
    nom: str
    libelle: str
    fichier: FormatFichier
    cle: Cle
    colonnes: tuple[Colonne, ...]
    filtre: str | None
    controles: Controles

    @property
    def mapping(self) -> dict[str, str]:
        """En-tete source -> nom de colonne normalise."""
        return {c.source: c.cible for c in self.colonnes}

    @property
    def cibles(self) -> tuple[str, ...]:
        return tuple(c.cible for c in self.colonnes)

    @property
    def colonnes_obligatoires(self) -> tuple[str, ...]:
        return tuple(c.cible for c in self.colonnes if c.obligatoire)

    def colonne(self, cible: str) -> Colonne:
        for c in self.colonnes:
            if c.cible == cible:
                return c
        raise ConfigurationInvalide(
            f"[{self.nom}] colonne inconnue : {cible!r}. Connues : {', '.join(self.cibles)}"
        )


def _lire_toml(chemin: Path) -> dict[str, Any]:
    with chemin.open("rb") as flux:
        return tomllib.load(flux)


def charger_schema(chemin: Path) -> SchemaRapport:
    brut = _lire_toml(chemin)
    try:
        colonnes = tuple(
            Colonne(
                source=c["source"],
                cible=c["cible"],
                type=c["type"],
                obligatoire=bool(c.get("obligatoire", False)),
            )
            for c in brut["colonnes"]
        )
        fichier = FormatFichier(**brut["fichier"])
        cle_brute = brut["cle"]
        cle = Cle(
            colonnes=tuple(cle_brute["colonnes"]),
            colonne_date=cle_brute["colonne_date"],
            colonnes_comparees=tuple(cle_brute.get("colonnes_comparees", ())),
        )
        ctrl = dict(brut.get("controles", {}))
        valeurs = {k: tuple(v) for k, v in ctrl.pop("valeurs_autorisees", {}).items()}
        controles = Controles(
            colonnes_non_nulles=tuple(ctrl.pop("colonnes_non_nulles", ())),
            unicite=tuple(ctrl.pop("unicite", ())),
            valeurs_autorisees=valeurs,
            **ctrl,
        )
    except KeyError as exc:
        raise ConfigurationInvalide(f"{chemin.name} : cle obligatoire manquante {exc}") from exc
    except TypeError as exc:
        raise ConfigurationInvalide(f"{chemin.name} : {exc}") from exc

    schema = SchemaRapport(
        nom=brut["nom"],
        libelle=brut.get("libelle", brut["nom"]),
        fichier=fichier,
        cle=cle,
        colonnes=colonnes,
        filtre=(brut.get("filtre", {}).get("expression") or None),
        controles=controles,
    )
    _valider_schema(schema, chemin)
    return schema


def _valider_schema(schema: SchemaRapport, chemin: Path) -> None:
    """Attrape les incoherences au chargement plutot qu'en plein traitement."""
    cibles = set(schema.cibles)

    inconnues = [c.cible for c in schema.colonnes if c.type not in TYPES_SUPPORTES]
    if inconnues:
        raise ConfigurationInvalide(
            f"{chemin.name} : type non supporte pour {inconnues}. "
            f"Types valides : {', '.join(sorted(TYPES_SUPPORTES))}"
        )

    doublons = [c for c in schema.cibles if schema.cibles.count(c) > 1]
    if doublons:
        raise ConfigurationInvalide(f"{chemin.name} : colonne cible en double {sorted(set(doublons))}")

    references = {
        "cle.colonnes": schema.cle.colonnes,
        "cle.colonne_date": (schema.cle.colonne_date,),
        "cle.colonnes_comparees": schema.cle.colonnes_comparees,
        "controles.colonnes_non_nulles": schema.controles.colonnes_non_nulles,
        "controles.unicite": schema.controles.unicite,
        "controles.valeurs_autorisees": tuple(schema.controles.valeurs_autorisees),
    }
    if schema.controles.mesure_totale:
        references["controles.mesure_totale"] = (schema.controles.mesure_totale,)

    for emplacement, noms in references.items():
        manquantes = [n for n in noms if n not in cibles]
        if manquantes:
            raise ConfigurationInvalide(
                f"{chemin.name} : {emplacement} reference des colonnes absentes du schema "
                f"{manquantes}. Colonnes declarees : {', '.join(sorted(cibles))}"
            )


# --------------------------------------------------------------------------
# Configuration globale
# --------------------------------------------------------------------------
@dataclass
class Config:
    reglages: dict[str, Any]
    schemas: dict[str, SchemaRapport]
    racine: Path

    def bloc(self, nom: str) -> dict[str, Any]:
        return self.reglages.get(nom, {})

    def schema(self, rapport: str) -> SchemaRapport:
        try:
            return self.schemas[rapport]
        except KeyError:
            raise ConfigurationInvalide(
                f"Rapport inconnu : {rapport!r}. Connus : {', '.join(sorted(self.schemas))}"
            ) from None

    @property
    def rapports(self) -> list[str]:
        return sorted(self.schemas)

    def chemin(self, cle: str) -> Path:
        """Resout un chemin de config, relatif a la racine projet si besoin."""
        valeur = Path(self.bloc("chemins")[cle]).expanduser()
        return valeur if valeur.is_absolute() else (self.racine / valeur)


def fusionner(base: dict[str, Any], surcharge: dict[str, Any]) -> dict[str, Any]:
    """Fusion recursive : la surcharge ne remplace que ce qu'elle mentionne."""
    resultat = dict(base)
    for cle, valeur in surcharge.items():
        if isinstance(valeur, dict) and isinstance(resultat.get(cle), dict):
            resultat[cle] = fusionner(resultat[cle], valeur)
        else:
            resultat[cle] = valeur
    return resultat


def charger(racine: Path | None = None) -> Config:
    racine = Path(racine or RACINE_PROJET).resolve()
    dossier_config = racine / "config"

    principal = dossier_config / "settings.toml"
    if not principal.exists():
        raise ConfigurationInvalide(f"Configuration introuvable : {principal}")
    reglages = _lire_toml(principal)

    local = dossier_config / "settings.local.toml"
    if local.exists():
        reglages = fusionner(reglages, _lire_toml(local))

    schemas: dict[str, SchemaRapport] = {}
    for chemin in sorted((dossier_config / "schemas").glob("*.toml")):
        schema = charger_schema(chemin)
        schemas[schema.nom] = schema

    if not schemas:
        raise ConfigurationInvalide(f"Aucun schema trouve dans {dossier_config / 'schemas'}")

    return Config(reglages=reglages, schemas=schemas, racine=racine)
