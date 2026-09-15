"""Genere des fichiers d'exemple pour essayer le script sans acces au site.

    python scripts/generer_exemple.py

Produit dans data/entrees/ :
  * activite_2026.xlsx   -- une ligne par dossier depuis le 1er janvier,
                            avec des colonnes supplementaires pour verifier
                            qu'elles sont bien ignorees ;
  * objectifs_2026.xlsx  -- une ligne par DR, deux colonnes d'objectif.

Les volumes sont deliberement inegaux entre DR, et une DR est en net retard,
pour que le graphique R/O montre quelque chose.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from rapports.config import charger  # noqa: E402
from rapports.semaines import dimanche_de, semaine_courante  # noqa: E402

SEGMENTS = ["Grand Public", "Pro", "Entreprise"]
DR = {
    "DR01": 1.25, "DR02": 1.10, "DR03": 0.98, "DR04": 0.90,
    "DR05": 0.72, "DR06": 1.05, "DR99": 1.00,
}
OBJECTIF_ANNUEL = 5200
# Part des segments retenus par le filtre de config/rapports.toml. L'objectif
# porte sur ce perimetre, sinon toutes les DR paraitraient en echec.
PART_SEGMENTS_RETENUS = 0.85


def main() -> int:
    cfg = charger(RACINE)
    dossier = cfg.dossier_entrees
    dossier.mkdir(parents=True, exist_ok=True)

    semaine = semaine_courante()
    fin = pd.Timestamp(dimanche_de(semaine))
    debut = pd.Timestamp(fin.year, 1, 1)
    jours = (fin - debut).days + 1
    part_annee = jours / 365

    alea = np.random.RandomState(20260915)
    lignes = []
    for code, performance in DR.items():
        # Volume attendu a date, module par la performance de la DR
        volume = int(OBJECTIF_ANNUEL * part_annee * performance)
        decalages = alea.randint(0, jours, volume)
        lignes.append(
            pd.DataFrame(
                {
                    "Date CAV": debut + pd.to_timedelta(decalages, unit="D"),
                    "Code DR": code,
                    "Segment": alea.choice(SEGMENTS, volume, p=[0.55, 0.30, 0.15]),
                    "Reference dossier": [f"{code}-{i:06d}" for i in range(volume)],
                    "Commentaire": "",  # colonne non declaree : doit etre ignoree
                }
            )
        )

    activite = pd.concat(lignes, ignore_index=True).sample(frac=1, random_state=1)
    chemin_activite = dossier / f"activite_{fin.year}.xlsx"
    activite.to_excel(chemin_activite, index=False)

    objectif_annuel = int(OBJECTIF_ANNUEL * PART_SEGMENTS_RETENUS)
    objectifs = pd.DataFrame(
        {
            "Code DR": list(DR),
            "Objectif debut annee": [int(objectif_annuel * part_annee)] * len(DR),
            "Objectif annuel": [objectif_annuel] * len(DR),
        }
    )
    chemin_objectifs = dossier / f"objectifs_{fin.year}.xlsx"
    objectifs.to_excel(chemin_objectifs, index=False)

    print(f"{chemin_activite}  ({len(activite)} lignes)")
    print(f"{chemin_objectifs}  ({len(objectifs)} DR)")
    print(f"\nEnchainer avec :  rapport run --semaine {semaine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
