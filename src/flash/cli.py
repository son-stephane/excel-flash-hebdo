"""Ligne de commande du flash hebdomadaire.

    flash run                      chaine complete sur la semaine courante
    flash run --semaine 2026-W37   sur une semaine precise
    flash etat                     que trouve-t-on comme fichiers ?
    flash detail --ou "..."        remonter aux lignes sources d'un chiffre

Chaque etape est aussi appelable seule : c'est ce qui permet de rejouer un
morceau sans tout refaire (utile en enquete).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import drill, pipeline
from .config import ConfigurationInvalide, charger
from .extract import portail, inbox
from .ingest import snapshots
from .logging_setup import configurer, journal
from .paths import Emplacements
from .publish import charts, excel, mail
from .quality import checks
from .transform import marts
from .weeks import SemaineInvalide, semaine_courante, valider

LOG = journal("cli")


def _parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="flash", description="Automatisation du flash hebdomadaire"
    )
    parseur.add_argument("--racine", type=Path, default=None, help="racine du projet")
    parseur.add_argument("-v", "--verbeux", action="store_true")
    sous = parseur.add_subparsers(dest="commande", required=True)

    def avec_semaine(p):
        p.add_argument("--semaine", default=None, help="semaine ISO, ex. 2026-W37")
        return p

    def avec_rapports(p):
        p.add_argument("--rapport", action="append", dest="rapports", help="limiter a ce rapport")
        return p

    sous.add_parser("init", help="creer l'arborescence de donnees")

    executer = avec_rapports(avec_semaine(sous.add_parser("run", help="chaine complete")))
    executer.add_argument("--sans-extraction", action="store_true",
                          help="ne pas tenter le telechargement, utiliser les fichiers presents")
    executer.add_argument("--sans-mail", action="store_true", help="ne pas preparer le mail")
    executer.add_argument("--sans-excel", action="store_true", help="ne pas produire le classeur")
    executer.add_argument("--forcer", action="store_true",
                          help="publier malgre des controles bloquants")

    avec_semaine(sous.add_parser("etat", help="fichiers disponibles pour la semaine"))
    avec_rapports(avec_semaine(sous.add_parser("extraire", help="telecharger depuis le portail")))

    ingerer = avec_rapports(avec_semaine(sous.add_parser("ingerer", help="brut -> snapshot Parquet")))
    ingerer.add_argument("--fichier", type=Path, default=None, help="fichier precis a ingerer")

    avec_rapports(avec_semaine(sous.add_parser("controler", help="controles qualite")))
    avec_semaine(sous.add_parser("mart", help="construire la table agregee"))
    avec_semaine(sous.add_parser("graphiques", help="generer les graphiques Python"))
    avec_semaine(sous.add_parser("classeur", help="produire le classeur Excel"))
    avec_semaine(sous.add_parser("mail", help="preparer le mail"))
    sous.add_parser("semaines", help="historique disponible")

    detail = avec_rapports(avec_semaine(sous.add_parser("detail", help="lignes sources d'un chiffre")))
    detail.add_argument("--ou", required=True, help="condition SQL, ex: \"categorie = 'Transport'\"")
    detail.add_argument("--limite", type=int, default=None)
    detail.add_argument("--sortie", type=Path, default=None)

    requete = avec_semaine(sous.add_parser("sql", help="requete libre sur les snapshots"))
    requete.add_argument("requete", help="SQL a executer")

    return parseur


def _semaine(args) -> str:
    return valider(getattr(args, "semaine", None) or semaine_courante())


def main(argv: list[str] | None = None) -> int:
    args = _parseur().parse_args(argv)

    try:
        cfg = charger(args.racine)
    except ConfigurationInvalide as exc:
        print(f"Configuration invalide : {exc}", file=sys.stderr)
        return 2

    lieux = Emplacements(cfg)
    configurer(lieux.logs(), verbeux=args.verbeux)

    try:
        return _executer(args, cfg, lieux)
    except (SemaineInvalide, ConfigurationInvalide) as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        return 2
    except (snapshots.FichierIntrouvable, snapshots.SchemaInattendu) as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1
    except (portail.EchecTelechargement, excel.TemplateInvalide, FileNotFoundError) as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130


def _executer(args, cfg, lieux: Emplacements) -> int:
    commande = args.commande

    if commande == "init":
        lieux.initialiser()
        print(f"Arborescence prete sous {lieux.racine}")
        return 0

    if commande == "semaines":
        for rapport in cfg.rapports:
            disponibles = lieux.semaines_disponibles(rapport)
            apercu = ", ".join(disponibles[-6:]) if disponibles else "aucune"
            print(f"{rapport:<12} {len(disponibles):>3} semaine(s)  dernieres : {apercu}")
        return 0

    semaine = _semaine(args)

    if commande == "etat":
        print(f"Semaine {semaine} -- dossiers consultes : "
              f"{lieux.raw(semaine)} et {lieux.inbox}\n")
        for etat in inbox.etat(cfg, semaine):
            print(etat)
        return 0

    if commande == "extraire":
        for resultat in portail.telecharger_tout(cfg, semaine, getattr(args, "rapports", None)):
            print(f"{resultat.rapport:<12} {resultat.chemin.name} ({resultat.octets / 1e6:.1f} Mo)")
        return 0

    if commande == "ingerer":
        for nom in args.rapports or cfg.rapports:
            resultat = snapshots.ingerer(cfg, nom, semaine, fichier=args.fichier)
            print(f"{resultat.rapport:<12} {resultat.lignes_conservees:>7} lignes conservees "
                  f"({resultat.lignes_filtrees} filtrees)")
        return 0

    if commande == "controler":
        rapport = checks.controler(cfg, semaine, getattr(args, "rapports", None))
        rapport.ecrire(cfg)
        for controle in rapport.controles:
            print(controle)
        print(f"\n{rapport.resume()}")
        return 1 if rapport.bloquant else 0

    if commande == "mart":
        table = marts.construire(cfg, semaine)
        print(f"{len(table)} lignes agregees -> {lieux.mart(semaine)}")
        return 0

    if commande == "graphiques":
        for chemin in charts.produire(cfg, semaine):
            print(chemin)
        return 0

    if commande == "classeur":
        resultat = excel.publier(cfg, semaine)
        print(f"Classeur : {resultat.classeur}")
        print(f"TCD rafraichis : {'oui' if resultat.tcd_rafraichis else 'non'}")
        for chemin in resultat.graphiques:
            print(f"  {chemin.name}")
        return 0

    if commande == "mail":
        graphiques = sorted(lieux.graphiques(semaine).glob("*.png"))
        if not graphiques:
            print("Aucun graphique : lancer d'abord `flash graphiques` ou `flash classeur`.",
                  file=sys.stderr)
            return 1
        classeur = lieux.classeur(semaine)
        resultat = mail.preparer(
            cfg, semaine, graphiques, classeur=classeur if classeur.exists() else None
        )
        print(resultat.resume())
        return 0

    if commande == "detail":
        resultats = drill.detailler(
            cfg, semaine, args.ou, rapports=args.rapports, limite=args.limite
        )
        for nom, lignes in resultats.items():
            print(f"{nom:<12} {len(lignes)} ligne(s)")
        print(f"\n{drill.exporter(cfg, semaine, resultats, args.sortie)}")
        return 0

    if commande == "sql":
        table = marts.requete_libre(cfg, args.requete, semaine)
        print(table.to_string(index=False, max_rows=100))
        return 0

    if commande == "run":
        resultat = pipeline.executer(
            cfg,
            semaine,
            extraire=not args.sans_extraction,
            diffuser=not args.sans_mail,
            avec_excel=not args.sans_excel,
            forcer=args.forcer,
            rapports=args.rapports,
        )
        print()
        print(resultat.resume())
        return 1 if resultat.arrete_par_controles else 0

    raise ConfigurationInvalide(f"Commande non geree : {commande}")


if __name__ == "__main__":
    sys.exit(main())
