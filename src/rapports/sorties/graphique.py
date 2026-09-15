"""Graphique du R/O par DR.

Barres verticales triees, une seule serie -- donc pas de legende : le titre
suffit a dire ce qui est represente. Chaque barre porte sa valeur, et un
trait de reference marque l'objectif a 100 %, qui est la seule comparaison
qui compte ici.

Les lignes de total sont volontairement exclues : elles ecraseraient la
lecture par DR, qui est l'objet du graphique.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # rendu fichier, aucune fenetre

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from ..calculs import Resultat  # noqa: E402
from ..semaines import libelle as libelle_semaine  # noqa: E402
from . import style  # noqa: E402


def produire(resultat: Resultat, chemin: Path) -> Path | None:
    donnees = resultat.par_dr.dropna(subset=["ro"]).sort_values("ro", ascending=False)
    if donnees.empty:
        return None

    largeur = max(7.0, 0.95 * len(donnees) + 2.0)
    fig, ax = plt.subplots(figsize=(largeur, 4.6), dpi=160)
    fig.patch.set_facecolor(style.FOND)
    ax.set_facecolor(style.FOND)

    barres = ax.bar(
        donnees["code_dr"], donnees["ro"], width=0.62, color=style.ROUGE, zorder=3
    )

    # Reference : l'objectif. C'est par rapport a ce trait que tout se lit.
    ax.axhline(1.0, color=style.NOIR, linewidth=1.2, linestyle="--", zorder=4)
    ax.annotate(
        "objectif",
        xy=(1.0, 1.0), xycoords=("axes fraction", "data"), xytext=(-4, 4),
        textcoords="offset points", ha="right", va="bottom",
        fontsize=8.5, color=style.NOIR,
    )

    ax.bar_label(
        barres,
        labels=[style.format_pourcent(v, 0) for v in donnees["ro"]],
        padding=4, fontsize=9, color=style.ENCRE_DOUCE,
    )

    _titre(ax, f"Realise / objectif par DR", f"{resultat.rapport.libelle} - {libelle_semaine(resultat.semaine)}")

    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f} %"))
    ax.set_ylim(0, max(1.15, float(donnees["ro"].max()) * 1.18))
    ax.yaxis.grid(True, color=style.TRAIT, linewidth=0.8, zorder=0)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    for cote in ("top", "right", "left"):
        ax.spines[cote].set_visible(False)
    ax.spines["bottom"].set_color(style.TRAIT)
    ax.tick_params(axis="both", length=0, labelsize=9, colors=style.ENCRE_DOUCE)

    chemin.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(chemin, bbox_inches="tight", pad_inches=0.28, facecolor=style.FOND)
    plt.close(fig)
    return chemin


def _titre(ax, titre: str, sous_titre: str) -> None:
    """Titre et sous-titre poses a decalage fixe : aucune collision possible."""
    ax.annotate(
        titre, xy=(0.008, 1), xycoords=("figure fraction", "axes fraction"),
        xytext=(0, 26), textcoords="offset points", ha="left", va="bottom",
        fontsize=13, fontweight="600", color=style.ENCRE,
    )
    ax.annotate(
        sous_titre, xy=(0.008, 1), xycoords=("figure fraction", "axes fraction"),
        xytext=(0, 11), textcoords="offset points", ha="left", va="bottom",
        fontsize=9.5, color=style.ENCRE_PALE,
    )
