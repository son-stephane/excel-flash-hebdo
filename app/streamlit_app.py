"""Interface du flash hebdomadaire.

Pensee pour une personne qui n'ecrit pas de code : elle ouvre un favori dans
son navigateur, clique sur un bouton, relit, envoie. Aucun fichier a executer.

Demarrage (une fois, par une tache planifiee "a l'ouverture de session") :

    streamlit run app/streamlit_app.py --server.port 8501

L'interface n'est qu'une facade : toute la logique vit dans flash.pipeline,
qui est aussi ce qu'appelle la ligne de commande et ce qu'appellera un job
planifie le jour ou le traitement passera en 100% automatique.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))

from flash import drill, pipeline  # noqa: E402
from flash.config import charger  # noqa: E402
from flash.extract import inbox  # noqa: E402
from flash.logging_setup import configurer  # noqa: E402
from flash.paths import Emplacements  # noqa: E402
from flash.publish import mail as module_mail  # noqa: E402
from flash.quality import checks  # noqa: E402
from flash.transform import marts  # noqa: E402
from flash.weeks import libelle, semaine_courante, semaine_precedente  # noqa: E402

st.set_page_config(page_title="Flash hebdomadaire", page_icon="📊", layout="wide")

PASTILLES = {checks.OK: "🟢", checks.ALERTE: "🟠", checks.ECHEC: "🔴"}


@st.cache_resource
def configuration():
    cfg = charger(RACINE)
    configurer(Emplacements(cfg).logs())
    return cfg


cfg = configuration()
lieux = Emplacements(cfg)

# --------------------------------------------------------------------------
with st.sidebar:
    st.title("Flash hebdomadaire")
    semaines_connues = sorted(
        {s for rapport in cfg.rapports for s in lieux.semaines_disponibles(rapport)},
        reverse=True,
    )
    courante = semaine_courante()
    choix = [courante] + [s for s in semaines_connues if s != courante]
    semaine = st.selectbox("Semaine", choix, index=0, help="Semaine ISO traitee")
    st.caption(libelle(semaine))

    st.divider()
    st.subheader("Options")
    extraire = st.checkbox("Telecharger depuis le portail", value=True)
    avec_excel = st.checkbox("Produire le classeur Excel", value=True)
    forcer = st.checkbox(
        "Publier malgre les controles", value=False,
        help="A n'utiliser que si l'anomalie a ete comprise et jugee acceptable.",
    )

onglet_traitement, onglet_enquete = st.tabs(["Traitement de la semaine", "Enqueter sur un chiffre"])

# --------------------------------------------------------------------------
with onglet_traitement:
    st.subheader("1. Fichiers disponibles")

    etats = inbox.etat(cfg, semaine)
    colonnes = st.columns(len(etats))
    for colonne, etat in zip(colonnes, etats):
        with colonne:
            if etat.present:
                taille = etat.fichier.stat().st_size / 1e6
                st.success(f"**{etat.rapport}**\n\n{etat.fichier.name}\n\n{taille:.1f} Mo")
            else:
                st.warning(f"**{etat.rapport}**\n\nmanquant\n\nmotif : `{etat.motif}`")

    with st.expander("Deposer un fichier a la main (si le portail est indisponible)"):
        depots = st.file_uploader(
            "Exports telecharges depuis le portail", accept_multiple_files=True,
            type=["csv", "xlsx"],
        )
        if depots:
            lieux.inbox.mkdir(parents=True, exist_ok=True)
            for fichier in depots:
                (lieux.inbox / fichier.name).write_bytes(fichier.getbuffer())
            st.success(f"{len(depots)} fichier(s) deposes dans {lieux.inbox}")
            st.rerun()

    st.divider()
    st.subheader("2. Traitement")

    if st.button("Lancer la semaine", type="primary", use_container_width=True):
        with st.status("Traitement en cours...", expanded=True) as statut:
            st.write("Ingestion, controles qualite, agregation, graphiques...")
            resultat = pipeline.executer(
                cfg, semaine,
                extraire=extraire, diffuser=False, avec_excel=avec_excel, forcer=forcer,
            )
            st.session_state["resultat"] = resultat
            statut.update(
                label="Traitement termine", state="complete" if not resultat.arrete_par_controles else "error"
            )

    resultat = st.session_state.get("resultat")
    if resultat is not None and resultat.semaine == semaine:
        if resultat.arrete_par_controles:
            st.error(
                "Le traitement a ete arrete par les controles qualite. "
                "Rien n'a ete diffuse. Voir le detail ci-dessous."
            )

        st.divider()
        st.subheader("3. Controles qualite")
        if resultat.controles:
            indicateurs = st.columns(3)
            indicateurs[0].metric("Conformes", sum(1 for c in resultat.controles.controles if c.niveau == checks.OK))
            indicateurs[1].metric("Alertes", len(resultat.controles.alertes))
            indicateurs[2].metric("Bloquants", len(resultat.controles.echecs))

            for controle in resultat.controles.controles:
                if controle.niveau == checks.OK:
                    continue
                st.write(f"{PASTILLES[controle.niveau]} **{controle.rapport}** — {controle.message}")
            with st.expander("Voir tous les controles"):
                st.dataframe(
                    [
                        {"rapport": c.rapport, "controle": c.nom, "niveau": c.niveau, "detail": c.message}
                        for c in resultat.controles.controles
                    ],
                    use_container_width=True, hide_index=True,
                )

        if resultat.graphiques:
            st.divider()
            st.subheader("4. Graphiques")
            for chemin in resultat.graphiques:
                st.image(str(chemin), use_container_width=True)

        st.divider()
        st.subheader("5. Diffusion")
        if resultat.arrete_par_controles and not forcer:
            st.info("Diffusion indisponible tant que les controles bloquants ne sont pas levés.")
        else:
            destinataires = cfg.bloc("mail").get("destinataires", [])
            st.write("Destinataires : " + ", ".join(destinataires))
            if st.button("Preparer le mail", use_container_width=True):
                envoi = module_mail.preparer(
                    cfg, semaine, resultat.graphiques,
                    controles=resultat.controles, classeur=resultat.classeur,
                )
                st.success(envoi.resume())
                if envoi.chemin:
                    st.download_button(
                        "Telecharger le mail (.eml)", envoi.chemin.read_bytes(),
                        file_name=envoi.chemin.name, mime="message/rfc822",
                    )

        if resultat.classeur and resultat.classeur.exists():
            st.download_button(
                "Telecharger le classeur Excel", resultat.classeur.read_bytes(),
                file_name=resultat.classeur.name, use_container_width=True,
            )

# --------------------------------------------------------------------------
with onglet_enquete:
    st.subheader("Remonter aux lignes sources")
    st.caption(
        "Un chiffre parait faux ? Filtrer ici pour retrouver les lignes exactes "
        "de l'export qui le composent."
    )

    filtre = st.text_input(
        "Condition", value="categorie = 'Transport' AND mois = '2026-03'",
        help="Condition SQL. Alias disponibles : mois ('AAAA-MM'), annee ('AAAA').",
    )
    if st.button("Rechercher"):
        resultats = drill.detailler(cfg, semaine, filtre, limite=5000)
        if not resultats:
            st.warning("Aucune ligne ne correspond.")
        for nom, lignes in resultats.items():
            st.write(f"**{nom}** — {len(lignes)} ligne(s)")
            st.dataframe(lignes.head(500), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Ce qui a change depuis la semaine precedente")
    precedente = semaine_precedente(semaine)
    chemin_diff = lieux.diff(cfg.rapports[0], semaine)
    if chemin_diff.exists():
        st.caption(f"Comparaison {precedente} → {semaine}")
        for rapport in cfg.rapports:
            chemin = lieux.diff(rapport, semaine)
            if not chemin.exists():
                continue
            import pandas as pd

            changements = pd.read_parquet(chemin)
            retroactifs = int(changements.get("retroactif", pd.Series(dtype=bool)).sum())
            st.write(
                f"**{rapport}** — {len(changements)} changement(s), "
                f"dont {retroactifs} sur des periodes deja publiees"
            )
            st.dataframe(changements.head(200), use_container_width=True, hide_index=True)
    else:
        st.info("Lancer d'abord le traitement de la semaine pour disposer de la comparaison.")

    st.divider()
    with st.expander("Requete SQL libre (avance)"):
        requete = st.text_area("SQL", value=f"SELECT * FROM rapport_a LIMIT 20")
        if st.button("Executer"):
            st.dataframe(marts.requete_libre(cfg, requete, semaine), use_container_width=True)
