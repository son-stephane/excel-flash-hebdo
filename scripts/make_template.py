"""Genere templates/flash_hebdo.xlsx : le classeur modele du flash.

    python scripts/make_template.py

Ce que le script produit :

  * un onglet DONNEES contenant un TABLEAU STRUCTURE (tbl_donnees). C'est le
    point cle : un TCD branche sur un tableau structure suit automatiquement
    la variation du nombre de lignes, alors qu'un TCD branche sur une plage
    figee (A1:J5000) ne la suit pas ;
  * un onglet SYNTHESE dont les formules SUMIFS se recalculent seules ;
  * un onglet GRAPHIQUES avec un graphique deja branche sur la synthese,
    pour que la chaine d'export produise quelque chose des le depart.

A FAIRE UNE FOIS, A LA MAIN, DANS EXCEL (openpyxl ne sait pas creer de TCD) :
  1. ouvrir le template ;
  2. Insertion > Tableau croise dynamique, source = tbl_donnees ;
  3. construire les TCD et graphiques voulus ;
  4. enregistrer. Le template est ensuite copie tel quel chaque semaine.
"""

from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from flash.config import charger  # noqa: E402

# Doit rester aligne avec transform/sql/mart_flash_hebdo.sql
COLONNES_MART = [
    "semaine_publication", "mois", "perimetre", "entite", "categorie", "statut",
    "nb_operations", "montant_total", "montant_moyen", "quantite_totale",
]

MOIS_SYNTHESE = 12
BLEU = "2a78d6"


def construire(chemin: Path, onglet_donnees: str, nom_tableau: str) -> Path:
    classeur = Workbook()

    donnees = classeur.active
    donnees.title = onglet_donnees
    donnees.append(COLONNES_MART)
    donnees.append([None] * len(COLONNES_MART))  # un tableau ne peut pas etre vide

    for cellule in donnees[1]:
        cellule.font = Font(bold=True, color="FFFFFF")
        cellule.fill = PatternFill("solid", fgColor=BLEU)
        cellule.alignment = Alignment(horizontal="center")
    for indice, nom in enumerate(COLONNES_MART, start=1):
        donnees.column_dimensions[get_column_letter(indice)].width = max(14, len(nom) + 2)
    donnees.freeze_panes = "A2"

    derniere_colonne = get_column_letter(len(COLONNES_MART))
    tableau = Table(displayName=nom_tableau, ref=f"A1:{derniere_colonne}2")
    tableau.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showRowStripes=True, showColumnStripes=False
    )
    donnees.add_table(tableau)

    synthese = classeur.create_sheet("SYNTHESE")
    synthese["A1"] = "mois"
    synthese["B1"] = "montant total"
    synthese["C1"] = "operations"
    for cellule in synthese[1]:
        cellule.font = Font(bold=True)

    for decalage in range(MOIS_SYNTHESE):
        ligne = 2 + decalage
        recul = -MOIS_SYNTHESE + 1 + decalage
        synthese[f"A{ligne}"] = (
            f"=IFERROR(EOMONTH(MAX({nom_tableau}[mois]),{recul})+1,\"\")"
        )
        synthese[f"A{ligne}"].number_format = "mmm yy"
        borne = f"EOMONTH(A{ligne},0)+1"
        synthese[f"B{ligne}"] = (
            f"=SUMIFS({nom_tableau}[montant_total],{nom_tableau}[mois],\">=\"&A{ligne},"
            f"{nom_tableau}[mois],\"<\"&{borne})"
        )
        synthese[f"B{ligne}"].number_format = "# ##0"
        synthese[f"C{ligne}"] = (
            f"=SUMIFS({nom_tableau}[nb_operations],{nom_tableau}[mois],\">=\"&A{ligne},"
            f"{nom_tableau}[mois],\"<\"&{borne})"
        )
        synthese[f"C{ligne}"].number_format = "# ##0"
    synthese.column_dimensions["A"].width = 14
    synthese.column_dimensions["B"].width = 16
    synthese.column_dimensions["C"].width = 14

    graphiques = classeur.create_sheet("GRAPHIQUES")
    graphiques["A1"] = "Graphiques du flash hebdomadaire"
    graphiques["A1"].font = Font(bold=True, size=13)
    graphiques["A2"] = (
        "Les graphiques de cet onglet sont exportes en PNG par `flash classeur`. "
        "Ajouter ici les TCD et graphiques voulus, branches sur le tableau "
        f"{nom_tableau} de l'onglet {onglet_donnees}."
    )
    graphiques["A2"].alignment = Alignment(wrap_text=True)
    graphiques.column_dimensions["A"].width = 100

    histogramme = BarChart()
    histogramme.type = "col"
    histogramme.title = "Montant total par mois"
    histogramme.height = 8
    histogramme.width = 20
    histogramme.y_axis.majorGridlines = None
    histogramme.add_data(
        Reference(synthese, min_col=2, min_row=1, max_row=1 + MOIS_SYNTHESE), titles_from_data=True
    )
    histogramme.set_categories(
        Reference(synthese, min_col=1, min_row=2, max_row=1 + MOIS_SYNTHESE)
    )
    graphiques.add_chart(histogramme, "A5")

    chemin.parent.mkdir(parents=True, exist_ok=True)
    classeur.save(chemin)
    return chemin


def main() -> int:
    cfg = charger(RACINE)
    reglages = cfg.bloc("excel")
    chemin = cfg.chemin("template_excel")

    if chemin.exists():
        reponse = input(f"{chemin} existe deja. Ecraser ? [o/N] ").strip().lower()
        if reponse not in ("o", "oui", "y"):
            print("Abandon : le template existant est conserve.")
            return 1

    construire(
        chemin,
        reglages.get("onglet_donnees", "DONNEES"),
        reglages.get("tableau_donnees", "tbl_donnees"),
    )
    print(f"Template genere : {chemin}")
    print("Ouvrir le fichier dans Excel pour y ajouter les TCD (source = tableau structure).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
