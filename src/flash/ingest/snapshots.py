"""Ingestion : fichier brut -> snapshot Parquet fige.

Trois responsabilites, dans cet ordre :
  1. verifier que le fichier a bien la structure attendue (sinon on refuse) ;
  2. typer les colonnes et appliquer le filtrage metier declare au schema ;
  3. ecrire un Parquet immuable dans la partition de la semaine.

Le refus en cas de schema inattendu est volontaire : c'est le mecanisme qui
detecte qu'une requete du portail a ete modifiee en amont sans prevenir, plutot
que de produire silencieusement un flash faux.
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..config import Config, SchemaRapport
from ..logging_setup import journal
from ..paths import Emplacements

LOG = journal("ingest")

COL_SEMAINE = "_semaine"
COL_EXTRACTION = "_date_extraction"
COL_FICHIER = "_fichier_source"
COL_HASH = "_hash_ligne"
COLONNES_TECHNIQUES = (COL_SEMAINE, COL_EXTRACTION, COL_FICHIER, COL_HASH)


class SchemaInattendu(RuntimeError):
    """Le fichier recu ne correspond pas au schema declare."""


class FichierIntrouvable(RuntimeError):
    pass


@dataclass
class ResultatIngestion:
    rapport: str
    semaine: str
    chemin_snapshot: Path
    lignes_lues: int
    lignes_conservees: int
    fichier_source: Path

    @property
    def lignes_filtrees(self) -> int:
        return self.lignes_lues - self.lignes_conservees


# --------------------------------------------------------------------------
# Reperage des fichiers
# --------------------------------------------------------------------------
def trouver_fichier(dossiers: list[Path], schema: SchemaRapport) -> Path:
    """Cherche le fichier du rapport dans les dossiers donnes, du plus recent au plus ancien."""
    candidats: list[Path] = []
    for dossier in dossiers:
        if not dossier.exists():
            continue
        for chemin in dossier.iterdir():
            if chemin.is_file() and fnmatch.fnmatch(chemin.name.lower(), schema.fichier.motif.lower()):
                candidats.append(chemin)

    if not candidats:
        emplacements = ", ".join(str(d) for d in dossiers)
        raise FichierIntrouvable(
            f"[{schema.nom}] aucun fichier correspondant a '{schema.fichier.motif}' "
            f"dans : {emplacements}"
        )

    candidats.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if len(candidats) > 1:
        LOG.warning(
            "[%s] %d fichiers candidats, le plus recent est retenu : %s",
            schema.nom, len(candidats), candidats[0].name,
        )
    return candidats[0]


def archiver_une_fois(fichier: Path, lieux: Emplacements, semaine: str, rapport: str) -> Path:
    """Place le fichier brut dans l'archive horodatee de la semaine.

    Deux precautions :

      * un fichier deja archive n'est pas recopie -- sinon chaque relance
        creerait un doublon de plus dans 00_raw ;
      * un fichier depose dans l'inbox en est RETIRE une fois archive. Sans
        cela, il serait encore trouve la semaine suivante et on rejouerait
        silencieusement des donnees perimees.
    """
    archive_semaine = lieux.raw(semaine)
    archive_semaine.mkdir(parents=True, exist_ok=True)

    if fichier.parent.resolve() == archive_semaine.resolve():
        LOG.debug("[%s] fichier deja archive : %s", rapport, fichier.name)
        return fichier

    horodatage = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = archive_semaine / f"{rapport}__{horodatage}{fichier.suffix}"
    shutil.copy2(fichier, destination)
    LOG.debug("[%s] archive brut : %s", rapport, destination)

    if fichier.parent.resolve() == lieux.inbox.resolve():
        fichier.unlink()
        LOG.info("[%s] %s retire de l'inbox (conserve dans %s)",
                 rapport, fichier.name, destination.parent)

    return destination


# --------------------------------------------------------------------------
# Lecture et typage
# --------------------------------------------------------------------------
def lire_brut(chemin: Path, schema: SchemaRapport) -> pd.DataFrame:
    fmt = schema.fichier
    if fmt.format == "csv":
        donnees = pd.read_csv(
            chemin,
            sep=fmt.separateur,
            encoding=fmt.encodage,
            decimal=fmt.decimal,
            dtype=str,
            keep_default_na=False,
            na_values=[""],
            engine="python",
        )
    elif fmt.format == "xlsx":
        # Volontairement SANS dtype=str : une cellule de type date d'Excel se
        # rendrait alors en "2026-03-12 00:00:00", que le format declare ne
        # saurait pas relire, et toute la colonne serait perdue. En la laissant
        # typee, elle traverse la conversion intacte. Pour un .xlsx, les
        # reglages separateur / encodage / decimal n'ont aucun effet.
        donnees = pd.read_excel(chemin)
    else:
        raise SchemaInattendu(f"[{schema.nom}] format non supporte : {fmt.format}")

    donnees.columns = [str(c).strip() for c in donnees.columns]
    return donnees


def verifier_structure(donnees: pd.DataFrame, schema: SchemaRapport, chemin: Path) -> None:
    attendues = set(schema.mapping)
    presentes = set(donnees.columns)

    manquantes = sorted(attendues - presentes)
    if manquantes:
        raise SchemaInattendu(
            f"[{schema.nom}] colonnes absentes de {chemin.name} : {manquantes}\n"
            f"  Colonnes trouvees : {sorted(presentes)}\n"
            f"  -> la requete du portail a probablement change. Mettre a jour "
            f"config/schemas/{schema.nom}.toml apres verification."
        )

    supplementaires = sorted(presentes - attendues)
    if supplementaires:
        LOG.warning(
            "[%s] colonnes supplementaires ignorees : %s", schema.nom, supplementaires
        )


def convertir(donnees: pd.DataFrame, schema: SchemaRapport) -> pd.DataFrame:
    """Renomme et type les colonnes selon le schema."""
    resultat = donnees[list(schema.mapping)].rename(columns=schema.mapping).copy()

    for colonne in schema.colonnes:
        serie = resultat[colonne.cible]
        if colonne.type == "string":
            resultat[colonne.cible] = serie.astype("string").str.strip()
        elif colonne.type == "date":
            if pd.api.types.is_datetime64_any_dtype(serie):
                # Deja une date (cellule Excel typee) : le format declare ne
                # s'applique pas, la valeur est prise telle quelle.
                converti = pd.to_datetime(serie, errors="coerce")
            else:
                converti = pd.to_datetime(
                    serie, format=schema.fichier.format_date, errors="coerce"
                )
            resultat[colonne.cible] = converti.dt.date
        elif colonne.type in ("int", "float"):
            nettoye = (
                serie.astype("string")
                .str.replace(" ", "", regex=False)   # espace insecable fin
                .str.replace("\xa0", "", regex=False)     # espace insecable
                .str.replace(" ", "", regex=False)
                .str.replace(schema.fichier.decimal, ".", regex=False)
            )
            numerique = pd.to_numeric(nettoye, errors="coerce")
            resultat[colonne.cible] = (
                numerique.astype("Int64") if colonne.type == "int" else numerique.astype("float64")
            )
        elif colonne.type == "bool":
            resultat[colonne.cible] = (
                serie.astype("string").str.lower().isin(["1", "true", "vrai", "oui", "o", "x"])
            )

        if colonne.obligatoire:
            fournies = int(serie.notna().sum())
            perdues = int(resultat[colonne.cible].isna().sum()) - int(serie.isna().sum())
            if perdues > 0 and perdues == fournies:
                # Aucune valeur n'a survecu : ce n'est pas un incident isole,
                # c'est le schema qui decrit mal le fichier. Mieux vaut refuser
                # que produire un snapshot vide dont personne ne verra le defaut.
                raise SchemaInattendu(_message_conversion(schema, colonne, serie))
            if perdues > 0:
                LOG.warning(
                    "[%s] %d valeurs de '%s' non convertibles en %s (mises a vide)",
                    schema.nom, perdues, colonne.cible, colonne.type,
                )

    return resultat


def _message_conversion(schema: SchemaRapport, colonne, serie: pd.Series) -> str:
    """Message d'erreur montrant ce qui a ete lu, pour corriger le schema."""
    echantillon = [repr(v) for v in serie.dropna().head(3).tolist()]
    detail = {
        "date": f"format_date = {schema.fichier.format_date!r}",
        "int": f"decimal = {schema.fichier.decimal!r}",
        "float": f"decimal = {schema.fichier.decimal!r}",
    }.get(colonne.type, "")
    return (
        f"[{schema.nom}] aucune valeur de '{colonne.cible}' (colonne source "
        f"{colonne.source!r}) n'a pu etre convertie en {colonne.type}.\n"
        f"  Valeurs lues : {', '.join(echantillon) or '(aucune)'}\n"
        f"  Reglage en cause : {detail}\n"
        f"  -> corriger le bloc [fichier] de config/schemas/{schema.nom}.toml."
    )


def appliquer_filtre(donnees: pd.DataFrame, schema: SchemaRapport) -> pd.DataFrame:
    if not schema.filtre:
        return donnees
    try:
        filtre = donnees.query(schema.filtre, engine="python")
    except Exception as exc:
        raise SchemaInattendu(
            f"[{schema.nom}] filtre invalide dans le schema : {schema.filtre!r} ({exc})"
        ) from exc
    LOG.info(
        "[%s] filtre '%s' : %d lignes ecartees", schema.nom, schema.filtre,
        len(donnees) - len(filtre),
    )
    return filtre.reset_index(drop=True)


def ajouter_metadonnees(
    donnees: pd.DataFrame, schema: SchemaRapport, semaine: str, fichier: Path
) -> pd.DataFrame:
    """Ajoute les colonnes techniques, dont le hash qui sert au diff N/N-1."""
    resultat = donnees.copy()
    resultat[COL_SEMAINE] = semaine
    resultat[COL_EXTRACTION] = pd.Timestamp.now().floor("s")
    resultat[COL_FICHIER] = fichier.name
    resultat[COL_HASH] = hacher(resultat, schema.cle.colonnes_comparees)
    return resultat


def hacher(donnees: pd.DataFrame, colonnes: tuple[str, ...]) -> pd.Series:
    """Empreinte stable des colonnes suivies, pour reperer les modifications."""
    if not colonnes:
        return pd.Series([""] * len(donnees), index=donnees.index, dtype="string")
    concatene = donnees[list(colonnes)].astype("string").fillna("\x00").agg("\x1f".join, axis=1)
    return concatene.map(
        lambda valeur: hashlib.blake2b(valeur.encode("utf-8"), digest_size=8).hexdigest()
    ).astype("string")


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def ingerer(
    cfg: Config,
    rapport: str,
    semaine: str,
    *,
    fichier: Path | None = None,
    remplacer: bool = True,
) -> ResultatIngestion:
    schema = cfg.schema(rapport)
    lieux = Emplacements(cfg)

    destination = lieux.snapshot(rapport, semaine)
    if destination.exists() and not remplacer:
        raise RuntimeError(
            f"[{rapport}] snapshot deja present pour {semaine} : {destination}\n"
            f"  Utiliser --remplacer pour le regenerer."
        )

    source = fichier or trouver_fichier([lieux.raw(semaine), lieux.inbox], schema)
    archive = archiver_une_fois(source, lieux, semaine, rapport)

    brut = lire_brut(archive, schema)
    verifier_structure(brut, schema, archive)
    type_ = convertir(brut, schema)
    filtre = appliquer_filtre(type_, schema)
    final = ajouter_metadonnees(filtre, schema, semaine, archive)

    Emplacements.preparer(destination)
    final.to_parquet(destination, index=False, compression="zstd")

    LOG.info(
        "[%s] %s : %d lignes conservees sur %d -> %s",
        rapport, semaine, len(final), len(brut), destination.name,
    )
    return ResultatIngestion(
        rapport=rapport,
        semaine=semaine,
        chemin_snapshot=destination,
        lignes_lues=len(brut),
        lignes_conservees=len(final),
        fichier_source=archive,
    )


def lire_snapshot(cfg: Config, rapport: str, semaine: str) -> pd.DataFrame:
    chemin = Emplacements(cfg).snapshot(rapport, semaine)
    if not chemin.exists():
        raise FichierIntrouvable(
            f"[{rapport}] pas de snapshot pour {semaine}. Lancer d'abord : "
            f"flash ingerer --semaine {semaine}"
        )
    return pd.read_parquet(chemin)
