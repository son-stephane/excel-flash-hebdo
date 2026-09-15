"""Rapport HTML autonome.

Le graphique est incorpore en base64 : le fichier n'a aucune dependance
externe, il peut donc etre envoye par mail, depose sur un partage ou ouvert
hors ligne sans rien perdre.
"""

from __future__ import annotations

import base64
import datetime as dt
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..calculs import LIGNE_DR, Resultat
from ..journal import journal
from ..semaines import dimanche_de
from ..semaines import libelle as libelle_semaine
from . import style

LOG = journal("html")

ENTETES = [
    "Code DR", "Réalisé semaine", "Réalisé cumul", "Objectif début année",
    "R/O", "Écart", "Objectif annuel", "% objectif annuel",
]


def produire(
    resultat: Resultat,
    chemin: Path,
    racine_gabarits: Path,
    graphique: Path | None = None,
    fichiers: dict[str, str] | None = None,
) -> Path:
    environnement = Environment(
        loader=FileSystemLoader(racine_gabarits),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    gabarit = environnement.get_template("rapport.html.j2")
    rapport = resultat.rapport

    page = gabarit.render(
        rapport=rapport,
        semaine=resultat.semaine,
        libelle_semaine=libelle_semaine(resultat.semaine),
        fin_periode=f"{dimanche_de(resultat.semaine):%d/%m/%Y}",
        segments=", ".join(rapport.segments) if rapport.segments else "tous",
        lignes_lues=style.format_entier(resultat.lignes_lues),
        lignes_retenues=style.format_entier(resultat.lignes_apres_filtre),
        entetes=ENTETES,
        lignes=[_ligne(ligne) for _, ligne in resultat.tableau.iterrows()],
        indicateurs=_indicateurs(resultat),
        graphique=_encoder(graphique),
        avertissements=resultat.avertissements,
        couleurs={
            "encre": style.ENCRE, "encre_douce": style.ENCRE_DOUCE,
            "encre_pale": style.ENCRE_PALE, "trait": style.TRAIT,
            "bleu": style.BLEU, "fond": style.FOND, "fond_doux": style.FOND_DOUX,
        },
        genere_le=dt.datetime.now().strftime("%d/%m/%Y a %H:%M"),
        fichier_source=(fichiers or {}).get("source", "—"),
        fichier_objectifs=(fichiers or {}).get("objectifs", "—"),
    )

    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(page, encoding="utf-8")
    LOG.info("Rapport HTML ecrit : %s", chemin)
    return chemin


def _ligne(ligne: pd.Series) -> dict:
    return {
        "code_dr": ligne["code_dr"],
        "realise_semaine": style.format_entier(ligne["realise_semaine"]),
        "realise_cumul": style.format_entier(ligne["realise_cumul"]),
        "objectif_debut_annee": style.format_entier(ligne["objectif_debut_annee"]),
        "ro": style.format_pourcent(ligne["ro"]),
        "ecart": style.format_ecart(ligne["ecart"]),
        "couleur_ecart": style.couleur_ecart(ligne["ecart"]),
        "objectif_annuel": style.format_entier(ligne["objectif_annuel"]),
        "part_annuel": style.format_pourcent(ligne["part_annuel"]),
        "est_total": ligne["type_ligne"] != LIGNE_DR,
    }


def _indicateurs(resultat: Resultat) -> list[dict]:
    total = resultat.total
    if total is None:
        return []

    indicateurs = [
        {
            "libelle": f"Réalisé cumul ({resultat.rapport.unite})",
            "valeur": style.format_entier(total["realise_cumul"]),
            "detail": f"dont {style.format_entier(total['realise_semaine'])} cette semaine",
            "couleur": style.ENCRE_DOUCE,
        },
        {
            "libelle": "R/O global",
            "valeur": style.format_pourcent(total["ro"]),
            "detail": f"{style.format_ecart(total['ecart'])} vs objectif",
            "couleur": style.couleur_ecart(total["ecart"]),
        },
        {
            "libelle": "Objectif début d'année",
            "valeur": style.format_entier(total["objectif_debut_annee"]),
            "detail": f"objectif annuel {style.format_entier(total['objectif_annuel'])}",
            "couleur": style.ENCRE_DOUCE,
        },
    ]

    hors = resultat.tableau[resultat.tableau["type_ligne"] == "total_hors"]
    if len(hors):
        ligne = hors.iloc[0]
        indicateurs.append(
            {
                "libelle": ligne["code_dr"],
                "valeur": style.format_pourcent(ligne["ro"]),
                "detail": f"{style.format_entier(ligne['realise_cumul'])} cumul",
                "couleur": style.couleur_ecart(ligne["ecart"]),
            }
        )
    return indicateurs


def _encoder(chemin: Path | None) -> str | None:
    if chemin is None or not chemin.exists():
        return None
    return base64.b64encode(chemin.read_bytes()).decode("ascii")
