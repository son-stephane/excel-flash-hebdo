"""Preparation et diffusion du mail hebdomadaire.

Par defaut, on cree un BROUILLON Outlook plutot que d'envoyer : le cout est
nul et cela evite d'envoyer un flash faux a toute une liste de diffusion.
Basculer ``mail.brouillon = false`` dans settings.toml une fois la confiance
etablie.

Hors Windows (ou sans Outlook), le mail est ecrit sur disque au format .eml :
double-cliquable, ouvrable dans Outlook, et surtout testable.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import Config
from ..logging_setup import journal
from ..paths import Emplacements
from ..quality.checks import ECHEC, RapportControles
from ..transform import marts
from ..weeks import libelle as libelle_semaine
from ..weeks import semaine_precedente
from .style import format_montant

LOG = journal("mail")

TITRES = {
    "01_montant_par_mois": "Montant total par mois",
    "02_montant_par_categorie": "Montant par categorie",
    "03_repartition_statut": "Repartition par statut",
    "04_evolution_publications": "Evolution entre publications",
}

VERT = "#008300"
ROUGE = "#e34948"
GRIS = "#7a7873"


@dataclass
class ResultatMail:
    chemin: Path | None
    destinataires: list[str]
    envoye: bool
    brouillon: bool

    def resume(self) -> str:
        if self.envoye:
            return f"mail envoye a {len(self.destinataires)} destinataire(s)"
        if self.chemin:
            return f"brouillon disponible : {self.chemin}"
        return "brouillon Outlook cree et affiche"


# --------------------------------------------------------------------------
def _environnement(cfg: Config) -> Environment:
    return Environment(
        loader=FileSystemLoader(cfg.racine / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def indicateurs(cfg: Config, semaine: str) -> list[dict]:
    """Trois chiffres cles, avec leur variation vs la publication precedente."""
    mart = marts.lire_mart(cfg, semaine)
    if mart.empty:
        return []

    montant = float(mart["montant_total"].sum())
    operations = int(mart["nb_operations"].sum())

    precedent = None
    chemin_precedent = Emplacements(cfg).mart(semaine_precedente(semaine))
    if chemin_precedent.exists():
        precedent = pd.read_parquet(chemin_precedent)

    def variation(actuel: float, colonne: str) -> tuple[str, str]:
        if precedent is None or precedent.empty:
            return "", GRIS
        reference = float(precedent[colonne].sum())
        if reference == 0:
            return "", GRIS
        ecart = (actuel - reference) / abs(reference) * 100
        return f"{ecart:+.1f}% vs semaine precedente", (VERT if ecart >= 0 else ROUGE)

    variation_montant, couleur_montant = variation(montant, "montant_total")
    variation_operations, couleur_operations = variation(operations, "nb_operations")

    return [
        {
            "libelle": "Montant total",
            "valeur": format_montant(montant),
            "variation": variation_montant,
            "couleur": couleur_montant,
        },
        {
            "libelle": "Operations",
            "valeur": f"{operations:,}".replace(",", " "),
            "variation": variation_operations,
            "couleur": couleur_operations,
        },
        {
            "libelle": "Perimetres",
            "valeur": str(mart["perimetre"].nunique()),
            "variation": "",
            "couleur": GRIS,
        },
    ]


def construire_corps(
    cfg: Config,
    semaine: str,
    graphiques: list[Path],
    controles: RapportControles | None,
    identifiants_images: dict[str, str],
) -> str:
    modele = _environnement(cfg).get_template("mail_flash.html.j2")
    alertes = [f"{c.rapport} - {c.message}" for c in (controles.alertes if controles else [])]

    return modele.render(
        semaine=semaine,
        libelle_semaine=libelle_semaine(semaine),
        date_extraction=dt.date.today().strftime("%d/%m/%Y"),
        indicateurs=indicateurs(cfg, semaine),
        graphiques=[
            {"cid": identifiants_images[g.stem], "titre": TITRES.get(g.stem, g.stem)}
            for g in graphiques
            if g.stem in identifiants_images
        ],
        alertes=alertes,
        note_bas_de_page=(
            "Genere automatiquement. Pour retrouver les lignes sources d'un chiffre : "
            f"flash detail --semaine {semaine} --ou \"categorie = '...'\""
        ),
    )


# --------------------------------------------------------------------------
def preparer(
    cfg: Config,
    semaine: str,
    graphiques: list[Path],
    *,
    controles: RapportControles | None = None,
    classeur: Path | None = None,
) -> ResultatMail:
    reglages = cfg.bloc("mail")
    destinataires = list(reglages.get("destinataires", []))
    if not destinataires:
        raise RuntimeError(
            "Aucun destinataire configure (mail.destinataires dans settings.local.toml)"
        )

    objet = reglages.get("objet", "Flash hebdomadaire - semaine {semaine}").format(
        semaine=semaine, libelle=libelle_semaine(semaine)
    )
    identifiants = {g.stem: make_msgid(domain="flash.local")[1:-1] for g in graphiques}
    corps = construire_corps(cfg, semaine, graphiques, controles, identifiants)

    pieces = []
    if classeur and reglages.get("joindre_classeur", True) and classeur.exists():
        pieces.append(classeur)

    brouillon = bool(reglages.get("brouillon", True))

    try:
        _via_outlook(cfg, objet, corps, destinataires, reglages, graphiques, identifiants, pieces, brouillon)
        return ResultatMail(None, destinataires, envoye=not brouillon, brouillon=brouillon)
    except OutlookIndisponible as exc:
        LOG.warning("Outlook non pilotable (%s) : ecriture d'un fichier .eml", exc)
        chemin = _via_eml(cfg, semaine, objet, corps, destinataires, reglages, graphiques, identifiants, pieces)
        return ResultatMail(chemin, destinataires, envoye=False, brouillon=True)


class OutlookIndisponible(RuntimeError):
    pass


def _via_outlook(
    cfg, objet, corps, destinataires, reglages, graphiques, identifiants, pieces, brouillon
) -> None:
    try:
        import win32com.client as com
    except ImportError as exc:
        raise OutlookIndisponible("pywin32 absent") from exc

    try:
        outlook = com.Dispatch("Outlook.Application")
        message = outlook.CreateItem(0)  # olMailItem
        message.Subject = objet
        message.To = "; ".join(destinataires)
        if reglages.get("copie"):
            message.CC = "; ".join(reglages["copie"])

        # Les images doivent etre jointes AVANT de fixer le HTMLBody, et
        # marquees avec leur Content-ID pour s'afficher dans le corps.
        for graphique in graphiques:
            piece = message.Attachments.Add(str(graphique.resolve()))
            piece.PropertyAccessor.SetProperty(
                "http://schemas.microsoft.com/mapi/proptag/0x3712001F",
                identifiants[graphique.stem],
            )
        for fichier in pieces:
            message.Attachments.Add(str(fichier.resolve()))

        message.HTMLBody = corps
        if brouillon:
            message.Save()
            message.Display(False)
            LOG.info("Brouillon Outlook cree et affiche")
        else:
            message.Send()
            LOG.info("Mail envoye a %s", ", ".join(destinataires))
    except Exception as exc:
        raise OutlookIndisponible(str(exc)) from exc


def _via_eml(
    cfg, semaine, objet, corps, destinataires, reglages, graphiques, identifiants, pieces
) -> Path:
    message = EmailMessage()
    message["Subject"] = objet
    message["From"] = reglages.get("expediteur") or "flash-hebdo@local"
    message["To"] = ", ".join(destinataires)
    if reglages.get("copie"):
        message["Cc"] = ", ".join(reglages["copie"])
    message.set_content("Ce message contient des graphiques : afficher en HTML.")
    message.add_alternative(corps, subtype="html")

    partie_html = message.get_payload()[-1]
    for graphique in graphiques:
        partie_html.add_related(
            graphique.read_bytes(), maintype="image", subtype="png",
            cid=f"<{identifiants[graphique.stem]}>", filename=graphique.name,
        )
    for fichier in pieces:
        message.add_attachment(
            fichier.read_bytes(),
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=fichier.name,
        )

    chemin = Emplacements.preparer(Emplacements(cfg).sorties(semaine) / f"flash_{semaine}.eml")
    chemin.write_bytes(bytes(message))
    LOG.info("Mail ecrit sur disque : %s", chemin)
    return chemin


# --------------------------------------------------------------------------
def alerter(cfg: Config, semaine: str, controles: RapportControles) -> None:
    """Previent l'equipe quand un controle bloquant a arrete le pipeline."""
    destinataires = cfg.bloc("alertes").get("destinataires", [])
    if not destinataires:
        LOG.warning("Aucun destinataire d'alerte configure : alerte non envoyee")
        return

    lignes = "\n".join(f"  - [{c.niveau}] {c.rapport} / {c.nom} : {c.message}" for c in controles.controles if c.niveau != "OK")
    texte = (
        f"Le flash de la semaine {semaine} a ete arrete par les controles qualite.\n\n"
        f"{lignes}\n\n"
        f"Rien n'a ete envoye aux destinataires.\n"
        f"Detail complet : {Emplacements(cfg).rapport_qualite(semaine)}\n"
    )

    try:
        import win32com.client as com

        outlook = com.Dispatch("Outlook.Application")
        message = outlook.CreateItem(0)
        message.Subject = f"[ALERTE] Flash hebdo {semaine} - controles en echec"
        message.To = "; ".join(destinataires)
        message.Body = texte
        message.Send()
        LOG.info("Alerte envoyee a %s", ", ".join(destinataires))
    except Exception as exc:
        chemin = Emplacements.preparer(Emplacements(cfg).sorties(semaine) / "ALERTE.txt")
        chemin.write_text(texte, encoding="utf-8")
        LOG.warning("Alerte non envoyee (%s). Ecrite dans %s", exc, chemin)
