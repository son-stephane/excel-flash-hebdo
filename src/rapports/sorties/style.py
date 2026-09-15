"""Apparence commune aux sorties : graphique, HTML et classeurs.

Couleurs et formats de nombres sont definis ici une seule fois, pour que le
tableau HTML, les classeurs et le graphique racontent visuellement la meme
chose. Changer la charte se fait donc a un seul endroit.

Contrastes verifies sur fond blanc (WCAG, rapport minimum 4.5:1 pour du
texte) : rouge 4.78:1, rouge fonce 8.09:1, gris texte 7.10:1, gris doux
4.54:1, vert 5.39:1, blanc sur rouge 4.78:1.
"""

from __future__ import annotations

import pandas as pd

# --- Charte ----------------------------------------------------------------
ROUGE = "#e60028"          # couleur d'accent : serie du graphique, en-tetes
ROUGE_SOMBRE = "#a4001c"   # ecart negatif : distinct de l'accent, plus dense
NOIR = "#000000"           # trait de reference, titres
ENCRE = "#000000"          # texte principal
ENCRE_DOUCE = "#58585a"    # texte secondaire
ENCRE_PALE = "#767676"     # mentions discretes
TRAIT = "#e3e3e1"          # grilles et filets
FOND = "#ffffff"
FOND_DOUX = "#f5f5f5"      # lignes de total
VERT = "#1a7a3c"           # ecart positif

# --- Formats Excel ---------------------------------------------------------
# Codes de format Excel : le separateur de milliers s'ecrit "," et le separateur
# decimal ".", quelle que soit la langue -- Excel les traduit a l'affichage
# selon la locale du poste (espace et virgule en francais).
FORMAT_ENTIER = "#,##0"
FORMAT_ECART = "+#,##0;-#,##0;0"
FORMAT_POURCENT = "0.0%"
FORMAT_DATE = "DD/MM/YYYY"


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
    """Vert au-dessus de l'objectif, rouge dense en dessous, neutre si inconnu."""
    if pd.isna(valeur):
        return ENCRE_PALE
    return VERT if valeur >= 0 else ROUGE_SOMBRE


def fleche_ecart(valeur) -> str:
    """Marqueur accompagnant la couleur.

    L'information ne doit jamais reposer sur la seule couleur : impression en
    noir et blanc, vision des couleurs deficiente, ou simplement un ecart
    affiche a cote d'une serie elle-meme rouge.
    """
    if pd.isna(valeur):
        return ""
    return "▲" if valeur >= 0 else "▼"
