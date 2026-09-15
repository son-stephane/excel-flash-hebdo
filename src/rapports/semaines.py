"""Semaines ISO.

Une semaine est designee par son identifiant ISO ``AAAA-Www`` (ex. 2026-W37).
C'est le seul format accepte : il se trie alphabetiquement dans l'ordre
chronologique, ce qui simplifie le nommage des fichiers produits.
"""

from __future__ import annotations

import datetime as dt
import re

_MOTIF = re.compile(r"^(\d{4})-W(\d{2})$")


class SemaineInvalide(ValueError):
    pass


def semaine_de(date: dt.date) -> str:
    annee, numero, _ = date.isocalendar()
    return f"{annee}-W{numero:02d}"


def semaine_courante(aujourdhui: dt.date | None = None) -> str:
    return semaine_de(aujourdhui or dt.date.today())


def lundi_de(semaine: str) -> dt.date:
    annee, numero = _decoupe(semaine)
    try:
        return dt.date.fromisocalendar(annee, numero, 1)
    except ValueError as exc:
        raise SemaineInvalide(f"Semaine inexistante : {semaine}") from exc


def dimanche_de(semaine: str) -> dt.date:
    return lundi_de(semaine) + dt.timedelta(days=6)


def bornes(semaine: str) -> tuple[dt.date, dt.date]:
    """(lundi, dimanche) de la semaine."""
    return lundi_de(semaine), dimanche_de(semaine)


def debut_annee(semaine: str) -> dt.date:
    """1er janvier de l'annee ISO de la semaine.

    Sert a delimiter le cumul depuis le debut de l'annee. On prend l'annee du
    LUNDI de la semaine : pour une semaine a cheval sur deux annees civiles,
    c'est elle qui fait foi cote metier.
    """
    return dt.date(lundi_de(semaine).year, 1, 1)


def libelle(semaine: str) -> str:
    """Ex. 'S37 - du 07/09 au 13/09/2026'."""
    debut, fin = bornes(semaine)
    _, numero = _decoupe(semaine)
    return f"S{numero:02d} - du {debut:%d/%m} au {fin:%d/%m/%Y}"


def valider(semaine: str) -> str:
    lundi_de(semaine)
    return semaine


def _decoupe(semaine: str) -> tuple[int, int]:
    trouve = _MOTIF.match(semaine or "")
    if not trouve:
        raise SemaineInvalide(
            f"Format attendu 'AAAA-Www' (ex. 2026-W37), recu : {semaine!r}"
        )
    return int(trouve.group(1)), int(trouve.group(2))
