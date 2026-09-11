"""Controles qualite executes AVANT toute publication.

Principe : si un controle bloquant echoue, rien n'est envoye aux
destinataires et une alerte part vers l'equipe. C'est ce qui transforme
"il arrive que les graphiques ne soient pas bons" en "on le sait avant eux".

La severite de chaque controle est declaree dans SEVERITES ci-dessous.
Passer un controle de ECHEC a ALERTE le rend non bloquant.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from ..config import Config
from ..ingest.snapshots import lire_snapshot
from ..logging_setup import journal
from ..paths import Emplacements
from ..weeks import dimanche_de
from . import diff as module_diff

LOG = journal("qualite")

OK = "OK"
ALERTE = "ALERTE"
ECHEC = "ECHEC"

SEVERITES: dict[str, str] = {
    "volumetrie_absolue": ECHEC,
    "variation_volumetrie": ECHEC,
    "colonnes_non_nulles": ECHEC,
    "unicite_cle": ECHEC,
    "variation_total": ECHEC,
    "valeurs_autorisees": ALERTE,
    "dates_invalides": ALERTE,
    "dates_futures": ALERTE,
    "changements_retroactifs": ALERTE,
}


@dataclass
class Controle:
    nom: str
    rapport: str
    niveau: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def bloquant(self) -> bool:
        return self.niveau == ECHEC

    def __str__(self) -> str:
        pastille = {OK: "[ OK ]", ALERTE: "[ !! ]", ECHEC: "[ KO ]"}[self.niveau]
        return f"{pastille} {self.rapport:<12} {self.nom:<26} {self.message}"


@dataclass
class RapportControles:
    semaine: str
    controles: list[Controle] = field(default_factory=list)

    @property
    def bloquant(self) -> bool:
        return any(c.bloquant for c in self.controles)

    @property
    def alertes(self) -> list[Controle]:
        return [c for c in self.controles if c.niveau == ALERTE]

    @property
    def echecs(self) -> list[Controle]:
        return [c for c in self.controles if c.niveau == ECHEC]

    def resume(self) -> str:
        return (
            f"{sum(1 for c in self.controles if c.niveau == OK)} OK, "
            f"{len(self.alertes)} alertes, {len(self.echecs)} echecs"
        )

    def en_dict(self) -> dict[str, Any]:
        return {
            "semaine": self.semaine,
            "genere_le": dt.datetime.now().isoformat(timespec="seconds"),
            "bloquant": self.bloquant,
            "resume": self.resume(),
            "controles": [
                {
                    "nom": c.nom,
                    "rapport": c.rapport,
                    "niveau": c.niveau,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.controles
            ],
        }

    def ecrire(self, cfg: Config) -> None:
        chemin = Emplacements.preparer(Emplacements(cfg).rapport_qualite(self.semaine))
        chemin.write_text(
            json.dumps(self.en_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        LOG.debug("Rapport de controles ecrit : %s", chemin)


def _niveau(nom: str, en_echec: bool) -> str:
    return SEVERITES.get(nom, ECHEC) if en_echec else OK


def _variation_pct(courant: float, reference: float) -> float | None:
    if reference in (0, None) or pd.isna(reference):
        return None
    return (courant - reference) / abs(reference) * 100.0


# --------------------------------------------------------------------------
def controler_rapport(cfg: Config, rapport: str, semaine: str) -> list[Controle]:
    schema = cfg.schema(rapport)
    regles = schema.controles
    donnees = lire_snapshot(cfg, rapport, semaine)
    resultats: list[Controle] = []

    def ajouter(nom: str, en_echec: bool, message: str, **details: Any) -> None:
        resultats.append(Controle(nom, rapport, _niveau(nom, en_echec), message, details))

    # 1. Volumetrie absolue
    lignes = len(donnees)
    hors_bornes = not (regles.lignes_min <= lignes <= regles.lignes_max)
    ajouter(
        "volumetrie_absolue",
        hors_bornes,
        f"{lignes:,} lignes (attendu entre {regles.lignes_min:,} et {regles.lignes_max:,})".replace(",", " "),
        lignes=lignes, min=regles.lignes_min, max=regles.lignes_max,
    )

    # 2. Colonnes obligatoires non nulles
    manquants = {
        colonne: int(donnees[colonne].isna().sum())
        for colonne in regles.colonnes_non_nulles
        if colonne in donnees and donnees[colonne].isna().any()
    }
    ajouter(
        "colonnes_non_nulles",
        bool(manquants),
        "aucune valeur manquante" if not manquants else f"valeurs manquantes : {manquants}",
        manquants=manquants,
    )

    # 3. Unicite de la clef metier
    if regles.unicite:
        doublons = int(donnees.duplicated(subset=list(regles.unicite)).sum())
        exemples = (
            donnees[donnees.duplicated(subset=list(regles.unicite), keep=False)][
                list(regles.unicite)
            ]
            .head(5)
            .to_dict("records")
        )
        ajouter(
            "unicite_cle",
            doublons > 0,
            f"{doublons} doublon(s) sur {list(regles.unicite)}",
            doublons=doublons, exemples=exemples,
        )

    # 4. Valeurs attendues (detecte une nouvelle modalite apparue en amont)
    for colonne, autorisees in regles.valeurs_autorisees.items():
        if colonne not in donnees:
            continue
        observees = set(donnees[colonne].dropna().unique()) - set(autorisees)
        ajouter(
            "valeurs_autorisees",
            bool(observees),
            f"{colonne} : "
            + ("valeurs conformes" if not observees else f"valeurs inattendues {sorted(observees)}"),
            colonne=colonne, inattendues=sorted(observees),
        )

    # 5. Dates exploitables et non futures
    colonne_date = schema.cle.colonne_date
    if colonne_date in donnees:
        dates = pd.to_datetime(donnees[colonne_date], errors="coerce")
        invalides = int(dates.isna().sum())
        ajouter(
            "dates_invalides", invalides > 0,
            f"{invalides} date(s) illisibles dans {colonne_date}", nombre=invalides,
        )
        limite = pd.Timestamp(dimanche_de(semaine))
        futures = int((dates > limite).sum())
        ajouter(
            "dates_futures", futures > 0,
            f"{futures} ligne(s) posterieures au {limite:%d/%m/%Y}", nombre=futures,
        )

    # 6. Comparaisons avec la semaine precedente
    precedente = module_diff.semaine_precedente_disponible(cfg, rapport, semaine)
    if precedente is None:
        resultats.append(
            Controle(
                "variation_volumetrie", rapport, OK,
                "premiere semaine historisee, aucune comparaison possible",
            )
        )
        return resultats

    ancien = lire_snapshot(cfg, rapport, precedente)
    variation = _variation_pct(len(donnees), len(ancien))
    if variation is not None:
        ajouter(
            "variation_volumetrie",
            abs(variation) > regles.variation_lignes_max_pct,
            f"{variation:+.1f}% de lignes vs {precedente} "
            f"(seuil {regles.variation_lignes_max_pct:.0f}%)",
            variation_pct=round(variation, 2), semaine_reference=precedente,
            lignes_avant=len(ancien), lignes_apres=len(donnees),
        )

    mesure = regles.mesure_totale
    if mesure and mesure in donnees and mesure in ancien:
        total_apres = float(pd.to_numeric(donnees[mesure], errors="coerce").sum())
        total_avant = float(pd.to_numeric(ancien[mesure], errors="coerce").sum())
        ecart = _variation_pct(total_apres, total_avant)
        if ecart is not None:
            ajouter(
                "variation_total",
                abs(ecart) > regles.variation_total_max_pct,
                f"total {mesure} {ecart:+.1f}% vs {precedente} "
                f"(seuil {regles.variation_total_max_pct:.0f}%)",
                variation_pct=round(ecart, 2), total_avant=total_avant, total_apres=total_apres,
            )

    return resultats


def controler_retroactivite(resultat: module_diff.ResultatDiff) -> Controle | None:
    """Signale les corrections de la source sur des periodes deja publiees."""
    if not resultat.disponible:
        return None
    nombre = resultat.retroactifs
    return Controle(
        "changements_retroactifs",
        resultat.rapport,
        _niveau("changements_retroactifs", nombre > 0),
        (
            "aucune correction retroactive"
            if nombre == 0
            else f"{nombre} ligne(s) de periodes deja publiees ont change depuis "
            f"{resultat.semaine_precedente}"
        ),
        {"nombre": nombre, "detail": resultat.resume()},
    )


def controler(
    cfg: Config, semaine: str, rapports: list[str] | None = None, *, avec_diff: bool = True
) -> RapportControles:
    rapport_global = RapportControles(semaine=semaine)
    for nom in rapports or cfg.rapports:
        rapport_global.controles.extend(controler_rapport(cfg, nom, semaine))
        if avec_diff:
            resultat = module_diff.comparer(cfg, nom, semaine)
            module_diff.ecrire(cfg, resultat)
            controle = controler_retroactivite(resultat)
            if controle is not None:
                rapport_global.controles.append(controle)
    return rapport_global
