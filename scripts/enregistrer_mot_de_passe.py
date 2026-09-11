"""Enregistre le mot de passe du portail dans le trousseau Windows.

    python scripts/enregistrer_mot_de_passe.py

Le mot de passe n'est jamais ecrit dans un fichier du projet : il vit dans le
Gestionnaire d'identification de Windows, chiffre pour le compte utilisateur.
A relancer quand le mot de passe change.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from flash.config import charger  # noqa: E402


def main() -> int:
    try:
        import keyring
    except ImportError:
        print("keyring n'est pas installe : pip install keyring", file=sys.stderr)
        return 1

    cfg = charger(RACINE)
    reglages = cfg.bloc("portail")
    service = reglages.get("service_keyring")
    identifiant = reglages.get("identifiant")

    if not service or not identifiant:
        print(
            "Renseigner portail.service_keyring et portail.identifiant dans "
            "config/settings.toml (ou settings.local.toml) avant de lancer ce script.",
            file=sys.stderr,
        )
        return 2

    print(f"Service  : {service}")
    print(f"Identifiant : {identifiant}")
    mot_de_passe = getpass.getpass("Mot de passe du portail (saisie masquee) : ")
    if not mot_de_passe:
        print("Saisie vide : rien n'a ete enregistre.", file=sys.stderr)
        return 1

    keyring.set_password(service, identifiant, mot_de_passe)
    print("Mot de passe enregistre dans le trousseau.")

    if keyring.get_password(service, identifiant) != mot_de_passe:
        print("Verification echouee : relire la configuration du trousseau.", file=sys.stderr)
        return 1
    print("Verification OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
