"""Verifie que tous les fichiers du projet sont arrives intacts.

    python verifier_integrite.py

A lancer immediatement apres le transfert, AVANT toute installation. Compare
chaque fichier a l'empreinte SHA-256 enregistree dans MANIFESTE.txt au moment
de la creation de l'archive, et signale ce qui manque, ce qui est tronque et
ce qui a ete modifie.

MANIFESTE.txt n'est pas versionne : il est produit au moment de fabriquer
l'archive de transfert. Sur un poste ou le projet est suivi par git,
`git status` remplit le meme role et ce script est inutile.

Ce controle existe parce que pytest ne peut pas le remplacer : la suite de
tests ne couvre pas les modules de publication, donc un fichier tronque dans
publish/ passe les tests et n'echoue qu'a l'execution, avec un message qui ne
designe pas la vraie cause.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent
MANIFESTE = RACINE / "MANIFESTE.txt"


def main() -> int:
    if not MANIFESTE.exists():
        print(f"MANIFESTE.txt introuvable a cote de {Path(__file__).name}", file=sys.stderr)
        return 2

    manquants: list[str] = []
    alteres: list[tuple[str, int, int]] = []
    verifies = 0

    for ligne in MANIFESTE.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        empreinte_attendue, taille_attendue, relatif = ligne.split(None, 2)
        chemin = RACINE / relatif

        if not chemin.exists():
            manquants.append(relatif)
            continue

        contenu = chemin.read_bytes()
        if hashlib.sha256(contenu).hexdigest() != empreinte_attendue:
            alteres.append((relatif, int(taille_attendue), len(contenu)))
        else:
            verifies += 1

    print(f"{verifies} fichier(s) conformes")

    if manquants:
        print(f"\n{len(manquants)} FICHIER(S) MANQUANT(S) :")
        for relatif in manquants:
            print(f"  - {relatif}")

    if alteres:
        print(f"\n{len(alteres)} FICHIER(S) ALTERE(S) :")
        for relatif, attendu, recu in alteres:
            ecart = "tronque" if recu < attendu else "modifie"
            print(f"  - {relatif:<50} {recu} octets recus, {attendu} attendus ({ecart})")

    if manquants or alteres:
        print("\nLe transfert est incomplet : refaire la copie de l'archive entiere.")
        return 1

    print("\nLe projet est complet et intact. Installation possible.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
