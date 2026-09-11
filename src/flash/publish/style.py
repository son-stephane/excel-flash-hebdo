"""Style commun des graphiques matplotlib.

Palette categorielle validee (separation daltonisme sur paires adjacentes,
plancher de chroma et de luminosite). Les slots sont attribues dans un ordre
FIXE : une serie garde sa couleur meme si une autre disparait du graphique.

Trois des teintes passent sous 3:1 de contraste sur fond blanc : la regle de
relief s'applique, d'ou les etiquettes de valeur visibles sur les barres.
"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

matplotlib.use("Agg")  # rendu fichier, aucun affichage interactif

SURFACE = "#ffffff"
TEXTE_PRINCIPAL = "#0b0b0b"
TEXTE_SECONDAIRE = "#52514e"
TEXTE_ATTENUE = "#7a7873"
GRILLE = "#e8e7e3"

# Ordre fixe. Ne jamais cycler au-dela : replier le surplus dans "Autres".
PALETTE = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4")
MAX_SERIES = len(PALETTE)

STATUTS = {  # couleurs stables par modalite, independantes de l'ordre d'apparition
    "Ouvert": PALETTE[0],
    "En cours": PALETTE[1],
    "Clos": PALETTE[2],
}


def couleur(indice: int) -> str:
    return PALETTE[indice % MAX_SERIES]


def appliquer_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "font.family": ["DejaVu Sans"],
            "font.size": 10,
            "text.color": TEXTE_PRINCIPAL,
            "axes.labelcolor": TEXTE_SECONDAIRE,
            "axes.edgecolor": GRILLE,
            "axes.linewidth": 0.8,
            "axes.titlesize": 13,
            "axes.titleweight": "600",
            "axes.titlecolor": TEXTE_PRINCIPAL,
            "axes.titlelocation": "left",
            "axes.titlepad": 14,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "xtick.color": TEXTE_SECONDAIRE,
            "ytick.color": TEXTE_SECONDAIRE,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "xtick.bottom": False,
            "ytick.left": False,
            "grid.color": GRILLE,
            "grid.linewidth": 0.8,
            "legend.frameon": False,
            "legend.fontsize": 9,
            "legend.labelcolor": TEXTE_SECONDAIRE,
            "lines.linewidth": 2.0,
            "lines.markersize": 5,
            "figure.autolayout": False,
        }
    )


def figure(titre: str, sous_titre: str = "", taille=(9.0, 4.6)):
    """Cree la figure. Titre et sous-titre sont poses en annotations au-dessus
    des axes, a des decalages fixes en points : aucune collision possible,
    quelle que soit la hauteur de la figure."""
    fig, ax = plt.subplots(figsize=taille, dpi=160)
    ax.annotate(
        titre, xy=(0.012, 1), xycoords=("figure fraction", "axes fraction"), xytext=(0, 26),
        textcoords="offset points", ha="left", va="bottom",
        fontsize=13, fontweight="600", color=TEXTE_PRINCIPAL,
    )
    if sous_titre:
        ax.annotate(
            sous_titre, xy=(0.012, 1), xycoords=("figure fraction", "axes fraction"), xytext=(0, 11),
            textcoords="offset points", ha="left", va="bottom",
            fontsize=9.5, color=TEXTE_ATTENUE,
        )
    return fig, ax


MOIS_COURTS = {
    1: "janv.", 2: "fevr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
    7: "juil.", 8: "aout", 9: "sept.", 10: "oct.", 11: "nov.", 12: "dec.",
}


def mois_court(horodatage) -> str:
    """Libelle de mois en francais, independant de la locale du systeme."""
    return f"{MOIS_COURTS[horodatage.month]} {horodatage.year % 100:02d}"


def grille_horizontale(ax) -> None:
    ax.yaxis.grid(True, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)


def grille_verticale(ax) -> None:
    ax.xaxis.grid(True, zorder=0)
    ax.yaxis.grid(False)
    ax.set_axisbelow(True)


def arrondir_barres(ax, *, horizontal: bool = False, rayon_px: float = 4.0) -> None:
    """Arrondit l'extremite "donnee" des barres, base carree.

    Le rayon est exprime en PIXELS. Une barre vit dans un espace anisotrope
    (millions d'euros en y, index de categorie en x) : on passe donc le rayon
    en unites x et on confie a ``mutation_aspect`` la conversion vers y, sinon
    l'arrondi s'etale sur toute la largeur du graphique.

    A appeler apres ``tight_layout`` et un ``draw``, quand la geometrie des
    axes est definitive.
    """
    figure_ = ax.get_figure()
    x_par_px, y_par_px = _unites_par_pixel(ax, figure_)
    if not x_par_px or not y_par_px:
        return
    rayon_x = rayon_px * x_par_px
    rayon_y = rayon_px * y_par_px
    aspect = y_par_px / x_par_px

    for patch in list(ax.patches):
        if not isinstance(patch, Rectangle) or isinstance(patch, FancyBboxPatch):
            continue
        x, y = patch.get_xy()
        largeur, hauteur = patch.get_width(), patch.get_height()
        # Trop courte pour etre arrondie proprement : on la laisse telle quelle.
        if horizontal:
            if largeur <= 2 * rayon_x or hauteur <= 2 * rayon_y:
                continue
        elif hauteur <= 2 * rayon_y or largeur <= 2 * rayon_x:
            continue

        couleur_fond = patch.get_facecolor()
        boite = FancyBboxPatch(
            (x, y), largeur, hauteur,
            boxstyle=f"round,pad=0,rounding_size={rayon_x}",
            mutation_aspect=aspect,
            linewidth=0, edgecolor="none", facecolor=couleur_fond,
            zorder=patch.get_zorder(),
        )
        if horizontal:
            cache = Rectangle((x, y), rayon_x, hauteur, facecolor=couleur_fond,
                              edgecolor="none", zorder=patch.get_zorder())
        else:
            cache = Rectangle((x, y), largeur, rayon_y, facecolor=couleur_fond,
                              edgecolor="none", zorder=patch.get_zorder())
        patch.remove()
        ax.add_patch(boite)
        ax.add_patch(cache)


def _unites_par_pixel(ax, figure_) -> tuple[float, float]:
    boite = ax.get_window_extent(renderer=figure_.canvas.get_renderer())
    etendue_x = ax.get_xlim()[1] - ax.get_xlim()[0]
    etendue_y = ax.get_ylim()[1] - ax.get_ylim()[0]
    return etendue_x / max(boite.width, 1), etendue_y / max(boite.height, 1)


def format_montant(valeur: float) -> str:
    """Format court et lisible : 1 234 -> 1,2 k ; 1 234 567 -> 1,2 M."""
    absolu = abs(valeur)
    if absolu >= 1e6:
        return f"{valeur / 1e6:,.1f} M".replace(".", ",")
    if absolu >= 1e3:
        return f"{valeur / 1e3:,.0f} k"
    return f"{valeur:,.0f}".replace(",", " ")


def axe_montants(ax, axe: str = "y") -> None:
    """Formate un axe en montants courts. Evite la notation 1e7, illisible."""
    from matplotlib.ticker import FuncFormatter

    formateur = FuncFormatter(lambda valeur, _: format_montant(valeur))
    (ax.yaxis if axe == "y" else ax.xaxis).set_major_formatter(formateur)


def pied_de_page(fig, texte: str) -> None:
    fig.text(0.01, 0.01, texte, fontsize=8, color=TEXTE_ATTENUE, ha="left", va="bottom")
