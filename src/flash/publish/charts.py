"""Graphiques generes en Python (phase 2).

Aucune dependance a Office : utilisable sur un serveur, dans un job planifie,
ou pour verifier le flash sans ouvrir Excel. Les memes donnees (le mart)
alimentent les graphiques du classeur, donc les deux moteurs racontent la
meme chose.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..config import Config
from ..logging_setup import journal
from ..paths import Emplacements
from ..transform import marts
from ..weeks import libelle as libelle_semaine
from . import style

LOG = journal("graphiques")

AUTRES = "Autres"
MOIS_AFFICHES = 12
CATEGORIES_AFFICHEES = 8


def produire(cfg: Config, semaine: str) -> list[Path]:
    """Genere tous les graphiques de la semaine et retourne leurs chemins."""
    style.appliquer_style()
    mart = marts.lire_mart(cfg, semaine)
    dossier = Emplacements(cfg).graphiques(semaine)
    dossier.mkdir(parents=True, exist_ok=True)

    fichiers: list[Path] = []
    for fabriquer in (
        _montant_par_mois,
        _top_categories,
        _repartition_statut,
    ):
        chemin = fabriquer(mart, semaine, dossier)
        if chemin is not None:
            fichiers.append(chemin)

    tendance = _evolution(marts.evolution(cfg), semaine, dossier)
    if tendance is not None:
        fichiers.append(tendance)

    LOG.info("%d graphique(s) generes dans %s", len(fichiers), dossier)
    return fichiers


def _ordre_statuts(colonnes) -> list:
    """Ordre du cycle de vie (Ouvert -> En cours -> Clos), le reste ensuite."""
    connus = [s for s in style.STATUTS if s in colonnes]
    return connus + [c for c in colonnes if c not in connus]


def _ecarter(valeurs: dict[str, float], ax, ecart_minimal: float = 0.055) -> dict[str, float]:
    """Ecarte verticalement des etiquettes trop proches, en gardant leur ordre."""
    etendue = ax.get_ylim()[1] - ax.get_ylim()[0]
    minimum = etendue * ecart_minimal
    ordonnees = sorted(valeurs.items(), key=lambda couple: couple[1])
    ajustees: dict[str, float] = {}
    precedente = None
    for nom, valeur in ordonnees:
        if precedente is not None and valeur - precedente < minimum:
            valeur = precedente + minimum
        ajustees[nom] = valeur
        precedente = valeur
    return ajustees


def _sauver(fig, chemin: Path, *, arrondir: bool | None = None, horizontal: bool = False) -> Path:
    """Finalise la geometrie, arrondit les barres, puis ecrit le PNG.

    L'ordre compte : les arrondis sont calcules en pixels, ils ont donc besoin
    d'axes dont la taille definitive est connue -- soit apres tight_layout et
    un premier rendu.
    """
    fig.tight_layout(rect=(0, 0.04, 1, 0.93))
    fig.canvas.draw()
    if arrondir:
        style.arrondir_barres(fig.axes[0], horizontal=horizontal)
    fig.savefig(chemin, bbox_inches="tight", pad_inches=0.28)
    plt.close(fig)
    return chemin


def _source(semaine: str) -> str:
    return f"Source : extraction du portail du {libelle_semaine(semaine)}"


# --------------------------------------------------------------------------
# 1. Magnitude dans le temps -> barres verticales, serie unique (pas de legende)
# --------------------------------------------------------------------------
def _montant_par_mois(mart: pd.DataFrame, semaine: str, dossier: Path) -> Path | None:
    if mart.empty:
        return None
    serie = (
        mart.groupby("mois", as_index=False)["montant_total"].sum()
        .sort_values("mois")
        .tail(MOIS_AFFICHES)
    )
    if serie.empty:
        return None

    fig, ax = style.figure(
        "Montant total par mois",
        f"{MOIS_AFFICHES} derniers mois - {libelle_semaine(semaine)}",
    )
    style.grille_horizontale(ax)

    etiquettes = [style.mois_court(pd.Timestamp(m)) for m in serie["mois"]]
    barres = ax.bar(etiquettes, serie["montant_total"], width=0.62, color=style.couleur(0))

    ax.margins(y=0.16)
    # Etiquettes visibles : exigees par la regle de relief (contraste < 3:1).
    ax.bar_label(
        barres, labels=[style.format_montant(v) for v in serie["montant_total"]],
        padding=4, fontsize=8.5, color=style.TEXTE_SECONDAIRE,
    )
    ax.set_yticklabels([])
    ax.yaxis.set_visible(False)
    style.pied_de_page(fig, _source(semaine))
    return _sauver(fig, dossier / "01_montant_par_mois.png", arrondir=True)


# --------------------------------------------------------------------------
# 2. Magnitude par identite -> barres horizontales triees
# --------------------------------------------------------------------------
def _top_categories(mart: pd.DataFrame, semaine: str, dossier: Path) -> Path | None:
    if mart.empty:
        return None
    serie = (
        mart.groupby("categorie", as_index=False)["montant_total"].sum()
        .sort_values("montant_total", ascending=False)
    )
    if serie.empty:
        return None

    # Ordre d'affichage (de bas en haut) : "Autres" toujours en dernier, puis
    # les categories de la plus petite a la plus grande. "Autres" n'est pas une
    # categorie comme les autres : il ne prend pas sa place dans le classement.
    tete = serie.head(CATEGORIES_AFFICHEES).sort_values("montant_total")
    reste = serie.iloc[CATEGORIES_AFFICHEES:]["montant_total"].sum()
    if reste > 0:
        tete = pd.concat(
            [pd.DataFrame([{"categorie": AUTRES, "montant_total": reste}]), tete],
            ignore_index=True,
        )

    fig, ax = style.figure(
        "Montant par categorie",
        f"{CATEGORIES_AFFICHEES} premieres categories, le reste regroupe",
        taille=(9.0, 0.45 * len(tete) + 1.9),
    )
    style.grille_verticale(ax)

    couleurs = [
        style.TEXTE_ATTENUE if nom == AUTRES else style.couleur(0) for nom in tete["categorie"]
    ]
    barres = ax.barh(tete["categorie"], tete["montant_total"], height=0.62, color=couleurs)

    ax.margins(x=0.18)
    ax.bar_label(
        barres, labels=[style.format_montant(v) for v in tete["montant_total"]],
        padding=5, fontsize=8.5, color=style.TEXTE_SECONDAIRE,
    )
    ax.xaxis.set_visible(False)
    style.pied_de_page(fig, _source(semaine))
    return _sauver(fig, dossier / "02_montant_par_categorie.png", arrondir=True, horizontal=True)


# --------------------------------------------------------------------------
# 3. Composition -> barres empilees, 2 px de fond entre segments
# --------------------------------------------------------------------------
def _repartition_statut(mart: pd.DataFrame, semaine: str, dossier: Path) -> Path | None:
    if mart.empty or "statut" not in mart:
        return None
    croise = (
        mart.pivot_table(
            index="mois", columns="statut", values="nb_operations", aggfunc="sum", fill_value=0
        )
        .sort_index()
        .tail(MOIS_AFFICHES)
    )
    if croise.empty:
        return None
    croise = croise[_ordre_statuts(croise.columns)]

    fig, ax = style.figure(
        "Repartition des operations par statut",
        "nombre d'operations par mois",
    )
    style.grille_horizontale(ax)

    etiquettes = [style.mois_court(pd.Timestamp(m)) for m in croise.index]
    cumul = pd.Series(0.0, index=croise.index)
    for indice, statut in enumerate(croise.columns):
        ax.bar(
            etiquettes, croise[statut], bottom=cumul, width=0.62, label=str(statut),
            color=style.STATUTS.get(str(statut), style.couleur(indice)),
            edgecolor=style.SURFACE, linewidth=2.0,  # respiration entre segments
        )
        cumul = cumul + croise[statut]

    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncols=len(croise.columns))
    ax.margins(y=0.12)
    style.pied_de_page(fig, _source(semaine))
    return _sauver(fig, dossier / "03_repartition_statut.png")


# --------------------------------------------------------------------------
# 4. Evolution entre publications -> lignes, etiquetees au dernier point
# --------------------------------------------------------------------------
def _evolution(donnees: pd.DataFrame, semaine: str, dossier: Path) -> Path | None:
    if donnees.empty or donnees["semaine_publication"].nunique() < 2:
        LOG.info("Moins de deux publications : graphique d'evolution ignore")
        return None

    croise = donnees.pivot_table(
        index="semaine_publication", columns="perimetre", values="montant_total", aggfunc="sum"
    ).sort_index()

    fig, ax = style.figure(
        "Evolution du montant total entre publications",
        "chaque point = ce que la publication de la semaine annoncait",
    )
    style.grille_horizontale(ax)

    for indice, perimetre in enumerate(croise.columns):
        serie = croise[perimetre]
        ax.plot(
            serie.index, serie.values, marker="o", color=style.couleur(indice),
            label=str(perimetre), markeredgecolor=style.SURFACE, markeredgewidth=1.5,
        )

    ax.margins(x=0.18, y=0.18)
    style.axe_montants(ax)

    # Etiquettes directes au dernier point : l'identite n'est jamais portee par
    # la seule couleur. Les positions sont ecartees quand deux series se
    # superposent, sinon les libelles se chevauchent.
    dernieres = {p: float(croise[p].iloc[-1]) for p in croise.columns}
    for indice, (perimetre, valeur) in enumerate(_ecarter(dernieres, ax).items()):
        ax.annotate(
            f"{perimetre}  {style.format_montant(dernieres[perimetre])}",
            xy=(len(croise) - 1, valeur), xytext=(10, 0), textcoords="offset points",
            va="center", fontsize=8.5, color=style.TEXTE_SECONDAIRE,
        )

    if len(croise.columns) >= 2:
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.22), ncols=len(croise.columns))
    if len(croise) > 8:
        ax.tick_params(axis="x", rotation=45)
    style.pied_de_page(fig, _source(semaine))
    return _sauver(fig, dossier / "04_evolution_publications.png")
