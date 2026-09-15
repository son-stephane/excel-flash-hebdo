"""Apparence commune aux trois sorties : graphique, HTML et Excel.

Les couleurs et les formats de nombres sont definis ici une seule fois, pour
que le tableau HTML, le classeur et le graphique racontent visuellement la
meme chose.

La palette est validee : ecart suffisant en vision normale comme en vision
des couleurs deficiente, et chroma/luminosite dans les bandes recommandees.
"""

from __future__ import annotations

import pandas as pd

# --- Couleurs --------------------------------------------------------------
BLEU = "#2a78d6"          # serie principale
ENCRE = "#0b0b0b"         # texte principal
ENCRE_DOUCE = "#52514e"   # texte secondaire
ENCRE_PALE = "#7a7873"    # mentions discretes
TRAIT = "#e8e7e3"         # grilles et filets
FOND = "#ffffff"
FOND_DOUX = "#fafaf9"     # lignes de total
VERT = "#008300"          # au-dessus de l'objectif
ROUGE = "#c0392b"         # en dessous de l'objectif

# --- Formats Excel ---------------------------------------------------------
# Codes de format Excel : le separateur de milliers s'ecrit "," et le separateur
# decimal ".", quelle que soit la langue -- Excel les traduit a l'affichage
# selon la locale du poste (espace et virgule en francais).
FORMAT_ENTIER = "#,##0"
FORMAT_ECART = "+#,##0;-#,##0;0"
FORMAT_POURCENT = "0.0%"


def format_entier(valeur) -> str:
    if pd.isna(valeur):
        return "—"
    return f"{int(round(valeur)):,}".replace(",", " ")


def format_ecart(valeur) -> str:
    if pd.isna(valeur):
        return "—"
    return f"{int(round(valeur)):+,}".replace(",", " ")


def format_pourcent(valeur, decimales: int = 1) -> str:
    if pd.isna(valeur):
        return "—"
    return f"{valeur * 100:.{decimales}f} %".replace(".", ",")


def couleur_ecart(valeur) -> str:
    """Vert au-dessus de l'objectif, rouge en dessous, neutre si inconnu."""
    if pd.isna(valeur):
        return ENCRE_PALE
    return VERT if valeur >= 0 else ROUGE
