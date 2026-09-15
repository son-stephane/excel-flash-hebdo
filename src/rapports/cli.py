"""Ligne de commande.

    rapport run                      tous les rapports, semaine courante
    rapport run --semaine 2026-W37   sur une semaine precise
    rapport run --rapport activite   un seul rapport
    rapport liste                    rapports configures
    rapport verifier                 les fichiers attendus sont-ils la ?
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import pipeline, sources
from .config import ConfigurationInvalide, charger
from .journal import configurer, journal
from .semaines import SemaineInvalide, semaine_courante, valider

LOG = journal("cli")


def _parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="rapport", description="Rapports hebdomadaires par DR"
    )
    parseur.add_argument("--racine", type=Path, default=None, help="racine du projet")
    parseur.add_argument("-v", "--verbeux", action="store_true")
    sous = parseur.add_subparsers(dest="commande", required=True)

    executer = sous.add_parser("run", help="produire les rapports")
    executer.add_argument("--semaine", default=None, help="semaine ISO, ex. 2026-W37")
    executer.add_argument(
        "--rapport", action="append", dest="rapports",
        help="limiter a ce rapport (repetable)",
    )

    sous.add_parser("liste", help="rapports configures")
    sous.add_parser("verifier", help="controler la presence des fichiers d'entree")
    return parseur


def main(argv: list[str] | None = None) -> int:
    args = _parseur().parse_args(argv)

    try:
        cfg = charger(args.racine)
    except ConfigurationInvalide as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    configurer(cfg.dossier_sorties / "_journal", verbeux=args.verbeux)

    try:
        return _executer(args, cfg)
    except (ConfigurationInvalide, SemaineInvalide) as exc:
        print(f"\nErreur : {exc}\n", file=sys.stderr)
        return 2
    except (sources.FichierIntrouvable, sources.ColonnesInattendues) as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130


def _executer(args, cfg) -> int:
    if args.commande == "liste":
        for nom in cfg.noms:
            rapport = cfg.rapport(nom)
            print(f"{nom:<16} {rapport.libelle}")
            print(f"{'':<16} source    : {rapport.fichier}")
            print(f"{'':<16} objectifs : {rapport.objectifs_fichier}")
            segments = ", ".join(rapport.segments) if rapport.segments else "tous"
            print(f"{'':<16} segments  : {segments}")
        return 0

    if args.commande == "verifier":
        complet = True
        print(f"Dossier des entrees : {cfg.dossier_entrees}\n")
        for nom in cfg.noms:
            rapport = cfg.rapport(nom)
            for motif, quoi in (
                (rapport.fichier, "source"),
                (rapport.objectifs_fichier, "objectifs"),
            ):
                try:
                    chemin = sources.trouver(cfg.dossier_entrees, motif, quoi)
                    taille = chemin.stat().st_size / 1e6
                    print(f"[ OK ] {nom:<14} {quoi:<10} {chemin.name} ({taille:.1f} Mo)")
                except sources.FichierIntrouvable:
                    complet = False
                    print(f"[ -- ] {nom:<14} {quoi:<10} manquant (motif : {motif})")
        return 0 if complet else 1

    if args.commande == "run":
        semaine = valider(args.semaine or semaine_courante())
        demandes = args.rapports or cfg.noms
        for nom in demandes:
            cfg.rapport(nom)  # valide le nom avant de commencer

        sorties = [pipeline.executer(cfg, nom, semaine) for nom in demandes]
        print()
        for sortie in sorties:
            print(sortie.resume())
            print()
        return 0

    raise ConfigurationInvalide(f"Commande non geree : {args.commande}")


if __name__ == "__main__":
    sys.exit(main())
