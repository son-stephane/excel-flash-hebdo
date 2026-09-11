"""Utilitaires de semaine ISO.

Toute la chaine designe une semaine par son identifiant ISO ``YYYY-Www``
(ex. ``2026-W37``). C'est le seul format accepte en entree des commandes,
et celui utilise pour nommer fichiers et dossiers : il se trie
alphabetiquement dans le bon ordre, ce qui simplifie tout le reste.
"""

from __future__ import annotations

import datetime as dt
import re

_MOTIF_SEMAINE = re.compile(r"^(\d{4})-W(\d{2})$")


class SemaineInvalide(ValueError):
    """Identifiant de semaine mal forme."""


def semaine_de(date: dt.date) -> str:
    """Retourne l'identifiant ISO de la semaine contenant ``date``."""
    annee, numero, _ = date.isocalendar()
    return f"{annee}-W{numero:02d}"


def semaine_courante(aujourdhui: dt.date | None = None) -> str:
    return semaine_de(aujourdhui or dt.date.today())

def semaine_precedente(semaine: str) -> str:
    return semaine_de(lundi_de(semaine) - dt.timedelta(days=7))


def lundi_de(semaine: str) -> dt.date:
    """Date du lundi de la semaine ISO donnee."""
    annee, numero = _decoupe(semaine)
    try:
        return dt.date.fromisocalendar(annee, numero, 1)
    except ValueError as exc:  # semaine 53 inexistante sur l'annee
        raise SemaineInvalide(f"Semaine inexistante : {semaine}") from exc


def dimanche_de(semaine: str) -> dt.date:
    return lundi_de(semaine) + dt.timedelta(days=6)


def bornes(semaine: str) -> tuple[dt.date, dt.date]:
    """(lundi, dimanche) de la semaine."""
    return lundi_de(semaine), dimanche_de(semaine)


def libelle(semaine: str) -> str:
    """Libelle lisible pour un humain, ex. 'S37 (08/09 au 14/09/2026)'."""
    debut, fin = bornes(semaine)
    _, numero = _decoupe(semaine)
    return f"S{numero:02d} ({debut:%d/%m} au {fin:%d/%m/%Y})"


def valider(semaine: str) -> str:
    """Verifie le format et retourne la semaine inchangee."""
    lundi_de(semaine)
    return semaine


def _decoupe(semaine: str) -> tuple[int, int]:
    correspondance = _MOTIF_SEMAINE.match(semaine or "")
    if not correspondance:
        raise SemaineInvalide(
            f"Format de semaine attendu 'AAAA-Www' (ex. 2026-W37), recu : {semaine!r}"
        )
    return int(correspondance.group(1)), int(correspondance.group(2))
