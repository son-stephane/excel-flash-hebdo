"""Genere des exports du portail FACTICES pour tester la chaine sans acces au site.

    python scripts/make_sample_data.py --semaines 2026-W35 2026-W36 2026-W37

Les fichiers sont ecrits dans data/00_raw/<semaine>/, exactement la ou un
telechargement reel les deposerait. Le generateur reproduit les deux
caracteristiques qui comptent pour tester le pipeline :

  * chaque export contient TOUT l'historique (et pas seulement la semaine) ;
  * d'une semaine a l'autre, quelques lignes anciennes sont CORRIGEES, ce qui
    permet de verifier que le diff N/N-1 les detecte bien.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from flash.config import SchemaRapport, charger  # noqa: E402
from flash.weeks import lundi_de, valider  # noqa: E402

ENTITES = ["Nord", "Sud", "Est", "Ouest", "Ile-de-France", "Export"]
CATEGORIES = [
    "Transport", "Maintenance", "Fournitures", "Prestations", "Energie",
    "Assurances", "Formation", "Logistique", "Informatique", "Divers",
]
SOUS_CATEGORIES = ["Standard", "Urgent", "Contrat cadre", "Hors contrat"]
STATUTS = ["Ouvert", "En cours", "Clos"]

VOLUMES = {"rapport_a": 20_000, "rapport_b": 20_000, "rapport_c": 70_000}


def base(schema: SchemaRapport, lignes: int, fin: pd.Timestamp) -> pd.DataFrame:
    """Population de depart, identique d'une semaine a l'autre (graine fixe)."""
    alea = np.random.RandomState(abs(hash(schema.nom)) % (2**31))
    debut = fin - pd.Timedelta(days=540)
    jours = (fin - debut).days

    donnees = pd.DataFrame(
        {
            "id_ligne": [f"{schema.nom[-1].upper()}{i:07d}" for i in range(1, lignes + 1)],
            "date_operation": debut + pd.to_timedelta(alea.randint(0, jours, lignes), unit="D"),
            "entite": alea.choice(ENTITES, lignes),
            "categorie": alea.choice(CATEGORIES, lignes, p=_poids(len(CATEGORIES))),
            "statut": alea.choice(STATUTS, lignes, p=[0.2, 0.3, 0.5]),
            "montant": np.round(alea.gamma(2.5, 420, lignes), 2),
            "quantite": alea.randint(1, 40, lignes),
        }
    )
    if "sous_categorie" in schema.cibles:
        donnees["sous_categorie"] = alea.choice(SOUS_CATEGORIES, lignes)
    if "delai_jours" in schema.cibles:
        donnees["delai_jours"] = alea.randint(0, 60, lignes)
    return donnees


def _poids(n: int) -> np.ndarray:
    poids = np.linspace(2.0, 0.4, n)
    return poids / poids.sum()


def nouvelles_lignes(
    schema: SchemaRapport, depart: int, nombre: int, semaine: str
) -> pd.DataFrame:
    """Lignes datees de la semaine traitee."""
    alea = np.random.RandomState(abs(hash(schema.nom + semaine)) % (2**31))
    lundi = pd.Timestamp(lundi_de(semaine))
    donnees = pd.DataFrame(
        {
            "id_ligne": [f"{schema.nom[-1].upper()}{i:07d}" for i in range(depart + 1, depart + nombre + 1)],
            "date_operation": lundi + pd.to_timedelta(alea.randint(0, 7, nombre), unit="D"),
            "entite": alea.choice(ENTITES, nombre),
            "categorie": alea.choice(CATEGORIES, nombre, p=_poids(len(CATEGORIES))),
            "statut": alea.choice(["Ouvert", "En cours"], nombre, p=[0.7, 0.3]),
            "montant": np.round(alea.gamma(2.5, 440, nombre), 2),
            "quantite": alea.randint(1, 40, nombre),
        }
    )
    if "sous_categorie" in schema.cibles:
        donnees["sous_categorie"] = alea.choice(SOUS_CATEGORIES, nombre)
    if "delai_jours" in schema.cibles:
        donnees["delai_jours"] = alea.randint(0, 60, nombre)
    return donnees


def corriger(donnees: pd.DataFrame, nombre: int, semaine: str) -> pd.DataFrame:
    """Applique des corrections retroactives, comme le ferait la source."""
    if nombre <= 0 or donnees.empty:
        return donnees
    alea = np.random.RandomState(abs(hash("corrections" + semaine)) % (2**31))
    indices = alea.choice(donnees.index, size=min(nombre, len(donnees)), replace=False)
    donnees.loc[indices, "montant"] = np.round(
        donnees.loc[indices, "montant"] * alea.uniform(0.7, 1.3, len(indices)), 2
    )
    passage_clos = indices[: len(indices) // 2]
    donnees.loc[passage_clos, "statut"] = "Clos"
    return donnees


def ecrire(donnees: pd.DataFrame, schema: SchemaRapport, destination: Path) -> Path:
    """Ecrit au format exact attendu par le schema (separateur, encodage, decimal)."""
    fmt = schema.fichier
    sortie = donnees.copy()
    sortie["date_operation"] = pd.to_datetime(sortie["date_operation"]).dt.strftime(
        fmt.format_date or "%d/%m/%Y"
    )
    inverse = {c.cible: c.source for c in schema.colonnes}
    sortie = sortie[[c.cible for c in schema.colonnes]].rename(columns=inverse)

    destination.parent.mkdir(parents=True, exist_ok=True)
    sortie.to_csv(
        destination, sep=fmt.separateur, index=False, encoding=fmt.encodage,
        decimal=fmt.decimal, float_format="%.2f",
    )
    return destination


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--semaines", nargs="+", required=True, help="semaines ISO, dans l'ordre")
    parseur.add_argument("--lignes", type=int, default=None,
                         help="taille de la population de depart (defaut : volumes reels)")
    parseur.add_argument("--nouvelles", type=int, default=400, help="lignes ajoutees par semaine")
    parseur.add_argument("--corrections", type=int, default=25,
                         help="lignes anciennes corrigees par semaine")
    args = parseur.parse_args()

    cfg = charger(RACINE)
    semaines = [valider(s) for s in args.semaines]

    for indice, semaine in enumerate(semaines):
        for nom in cfg.rapports:
            schema = cfg.schema(nom)
            lignes = args.lignes or VOLUMES.get(nom, 20_000)
            fin = pd.Timestamp(lundi_de(semaines[0]))

            donnees = base(schema, lignes, fin)
            for passe in range(indice + 1):
                donnees = pd.concat(
                    [donnees, nouvelles_lignes(schema, len(donnees), args.nouvelles, semaines[passe])],
                    ignore_index=True,
                )
            donnees = corriger(donnees, args.corrections * indice, semaine)

            # Quelques annulations, que le filtre du schema doit ecarter.
            alea = np.random.RandomState(indice + 7)
            annulees = alea.choice(donnees.index, size=max(1, len(donnees) // 200), replace=False)
            donnees.loc[annulees, "statut"] = "Annule"

            chemin = ecrire(
                donnees, schema,
                cfg.chemin("racine_donnees") / "00_raw" / semaine / f"{nom}_export.csv",
            )
            print(f"{semaine}  {nom:<12} {len(donnees):>7} lignes -> {chemin}")

    print("\nEnchainer avec :  python -m flash run --semaine "
          f"{semaines[0]} --sans-extraction --sans-mail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
