"""Telechargement automatise des rapports du portail (Playwright).

C'EST LA PARTIE LA PLUS FRAGILE DU PROJET. Elle depend d'une interface web
qui peut changer sans preavis. Trois precautions structurent ce module :

  1. Tous les selecteurs sont regroupes dans SELECTEURS ci-dessous : quand
     le portail evolue, il n'y a qu'un seul endroit a corriger.
  2. Le contexte navigateur est PERSISTANT : le SSO/MFA n'est repasse que
     lorsque la session expire, pas a chaque execution.
  3. En cas d'echec, une capture d'ecran et le HTML de la page sont ecrits
     dans les sorties de la semaine, pour diagnostiquer sans rejouer.

Le mot de passe n'est JAMAIS stocke dans le code ni dans un fichier : il est
lu dans le trousseau Windows. L'enregistrer une fois avec :

    python -c "import keyring; keyring.set_password('flash-hebdo/portail', 'prenom.nom', 'LE_MOT_DE_PASSE')"
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..logging_setup import journal
from ..paths import Emplacements

LOG = journal("portail")

# ---------------------------------------------------------------------------
# A ADAPTER : selecteurs de l'interface du portail.
# Les relever une fois avec `playwright codegen <url>`, puis les coller ici.
# ---------------------------------------------------------------------------
SELECTEURS = {
    "champ_identifiant": "#username",
    "champ_mot_de_passe": "#password",
    "bouton_connexion": "button[type=submit]",
    "indicateur_connecte": "#menu-principal",
    "lien_requetes": "text=Requetes",
    "champ_recherche_requete": "input[name=recherche]",
    "resultat_requete": "tr:has-text('{requete}')",
    "bouton_executer": "button:has-text('Executer')",
    "indicateur_fin_execution": "text=Execution terminee",
    "bouton_telecharger": "button:has-text('Telecharger')",
}


class EchecTelechargement(RuntimeError):
    pass


@dataclass
class ResultatTelechargement:
    rapport: str
    chemin: Path
    octets: int


class SessionPortail:
    """Contexte navigateur persistant vers le portail."""

    def __init__(self, cfg: Config, semaine: str) -> None:
        self.cfg = cfg
        self.semaine = semaine
        self.reglages = cfg.bloc("portail")
        self.lieux = Emplacements(cfg)
        self._playwright = None
        self._contexte = None
        self.page = None

    # -- cycle de vie ------------------------------------------------------
    def __enter__(self) -> SessionPortail:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise EchecTelechargement(
                "Playwright absent. Installer avec :\n"
                "  pip install playwright && playwright install chromium"
            ) from exc

        profil = Path(self.reglages.get("profil_navigateur", ".playwright-profile"))
        if not profil.is_absolute():
            profil = self.cfg.racine / profil
        profil.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._contexte = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profil),
            headless=bool(self.reglages.get("sans_interface", False)),
            accept_downloads=True,
        )
        self._contexte.set_default_timeout(int(self.reglages.get("timeout_ms", 120_000)))
        self.page = self._contexte.pages[0] if self._contexte.pages else self._contexte.new_page()
        return self

    def __exit__(self, *_) -> None:
        if self._contexte is not None:
            self._contexte.close()
        if self._playwright is not None:
            self._playwright.stop()

    # -- navigation --------------------------------------------------------
    def connecter(self) -> None:
        """Ouvre le portail. Ne ressaisit les identifiants que si la session a expire."""
        self.page.goto(self.reglages["url_connexion"])

        if self.page.locator(SELECTEURS["indicateur_connecte"]).count():
            LOG.info("Session du portail deja active (profil persistant)")
            return

        identifiant = self.reglages.get("identifiant")
        mot_de_passe = self._mot_de_passe(identifiant)
        if not mot_de_passe:
            LOG.warning(
                "Aucun mot de passe dans le trousseau : connexion manuelle attendue "
                "dans la fenetre du navigateur (MFA, SSO...)."
            )
        else:
            self.page.fill(SELECTEURS["champ_identifiant"], identifiant)
            self.page.fill(SELECTEURS["champ_mot_de_passe"], mot_de_passe)
            self.page.click(SELECTEURS["bouton_connexion"])

        # Laisse le temps a une eventuelle validation MFA cote utilisateur.
        self.page.wait_for_selector(SELECTEURS["indicateur_connecte"])
        LOG.info("Connexion au portail etablie")

    def _mot_de_passe(self, identifiant: str | None) -> str | None:
        if not identifiant:
            return None
        try:
            import keyring
        except ImportError:
            LOG.warning("keyring absent : impossible de lire le trousseau")
            return None
        return keyring.get_password(self.reglages.get("service_keyring", ""), identifiant)

    def telecharger(self, rapport: str, requete: str) -> ResultatTelechargement:
        """Execute une requete et recupere le fichier produit."""
        LOG.info("[%s] execution de la requete %s", rapport, requete)
        try:
            self.page.click(SELECTEURS["lien_requetes"])
            self.page.fill(SELECTEURS["champ_recherche_requete"], requete)
            self.page.click(SELECTEURS["resultat_requete"].format(requete=requete))
            self.page.click(SELECTEURS["bouton_executer"])
            self.page.wait_for_selector(SELECTEURS["indicateur_fin_execution"])

            with self.page.expect_download() as attente:
                self.page.click(SELECTEURS["bouton_telecharger"])
            telechargement = attente.value
        except Exception as exc:
            self._capturer_pour_diagnostic(rapport)
            raise EchecTelechargement(
                f"[{rapport}] echec sur le portail : {exc}\n"
                f"  Capture et HTML de la page dans {self.lieux.sorties(self.semaine)}\n"
                f"  Si l'interface a change, corriger SELECTEURS dans extract/portail.py.\n"
                f"  Mode degrade : telecharger le fichier a la main et le deposer dans "
                f"{self.lieux.inbox}"
            ) from exc

        destination = self.lieux.raw(self.semaine)
        destination.mkdir(parents=True, exist_ok=True)
        suffixe = Path(telechargement.suggested_filename).suffix or ".csv"
        horodatage = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        chemin = destination / f"{rapport}__{horodatage}{suffixe}"
        telechargement.save_as(str(chemin))

        octets = chemin.stat().st_size
        if octets == 0:
            raise EchecTelechargement(f"[{rapport}] fichier telecharge vide : {chemin}")
        LOG.info("[%s] telecharge : %s (%.1f Mo)", rapport, chemin.name, octets / 1e6)
        return ResultatTelechargement(rapport, chemin, octets)

    def _capturer_pour_diagnostic(self, rapport: str) -> None:
        dossier = self.lieux.sorties(self.semaine)
        dossier.mkdir(parents=True, exist_ok=True)
        try:
            self.page.screenshot(path=str(dossier / f"echec_{rapport}.png"), full_page=True)
            (dossier / f"echec_{rapport}.html").write_text(self.page.content(), encoding="utf-8")
        except Exception:  # le diagnostic ne doit jamais masquer l'erreur d'origine
            LOG.debug("Capture de diagnostic impossible")


def telecharger_tout(
    cfg: Config, semaine: str, rapports: list[str] | None = None
) -> list[ResultatTelechargement]:
    demandes = {r["nom"]: r["requete"] for r in cfg.bloc("portail").get("rapports", [])}
    if rapports:
        demandes = {nom: req for nom, req in demandes.items() if nom in rapports}
    if not demandes:
        raise EchecTelechargement("Aucun rapport a telecharger (voir portail.rapports)")

    resultats: list[ResultatTelechargement] = []
    with SessionPortail(cfg, semaine) as session:
        session.connecter()
        for nom, requete in demandes.items():
            resultats.append(session.telecharger(nom, requete))
    return resultats
