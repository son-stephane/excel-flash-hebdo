# Mise en production

## Installation sur le poste Windows

```powershell
cd C:\chemin\vers\excel-flash-hebdo
python -m venv .venv
.venv\Scripts\pip install -e ".[windows,dev]"
.venv\Scripts\playwright install chromium
.venv\Scripts\python -m flash init
```

Puis enregistrer le mot de passe du portail dans le trousseau Windows — il n'est
jamais écrit dans un fichier du projet :

```powershell
.venv\Scripts\python scripts\enregistrer_mot_de_passe.py
```

## Configuration du poste

Créer `config/settings.local.toml` (non versionné) avec ce qui est propre à
l'environnement réel :

```toml
[chemins]
racine_donnees = "C:/Users/<user>/<Entreprise>/Flash hebdo - Documents/data"

[portail]
url_connexion = "https://portail.<entreprise>.fr/login"
identifiant = "prenom.nom"

[mail]
destinataires = ["equipe@entreprise.fr"]
expediteur = "prenom.nom@entreprise.fr"

[alertes]
destinataires = ["prenom.nom@entreprise.fr"]
```

### Le dossier SharePoint

Pointer `racine_donnees` vers un dossier **synchronisé localement** par le
client OneDrive, pas vers une URL `https://…sharepoint.com/…`. Le pipeline
écrit des fichiers, il lui faut un chemin de système de fichiers.

Le stockage est conçu pour cette synchro : les fichiers Parquet sont écrits une
fois et jamais réécrits, ce que OneDrive gère bien. À l'inverse, n'y placez
jamais un fichier de base unique réécrit à chaque exécution (`.duckdb`,
`.accdb`, un classeur qui s'empile) : c'est la recette des « copies en
conflit ».

Pour que les fichiers soient réellement présents sur disque et non seulement
« disponibles en ligne », marquer le dossier **Toujours conserver sur cet
appareil** dans l'explorateur.

## Les trois niveaux d'automatisation

Le pipeline est une commande unique (`python -m flash run`) appelée aussi bien
par la ligne de commande, par l'interface Streamlit que par le planificateur.
C'est ce qui permet de passer d'un niveau au suivant **sans rien réécrire**.

| Niveau | Infrastructure | Ce que fait l'utilisateur |
|---|---|---|
| **A. Assisté** | son poste + tâche au logon qui démarre l'interface | ouvre son favori, clique « Lancer », relit, envoie |
| **B. Semi-auto** | son poste + tâche hebdomadaire | reçoit un mail « flash prêt », vérifie, envoie le brouillon |
| **C. Automatique** | VM toujours allumée, compte de service | rien |

Démarrer en A, concevoir pour C. Le jour où la VM est obtenue, on branche le
planificateur sur la même commande.

### Installer les tâches planifiées

```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer_taches.ps1
```

Deux tâches sont créées :

- **Flash hebdo - interface** — à l'ouverture de session, démarre Streamlit en
  arrière-plan. L'utilisateur n'exécute rien : il a un favori navigateur vers
  `http://localhost:8501`. C'est la réponse au fait que les `.bat` sont
  généralement bloqués par la politique d'entreprise — il n'y a plus de script
  à lancer du tout.
- **Flash hebdo - traitement** — chaque lundi matin, prépare le flash sans le
  diffuser. **Désactivée par défaut** ; l'activer quand la chaîne est fiable :

  ```powershell
  Enable-ScheduledTask -TaskName "Flash hebdo - traitement"
  ```

### Limite du 100 % automatique

Playwright a besoin d'un vrai navigateur, donc d'une session ouverte. Sur le
poste de l'utilisateur, la tâche ne s'exécutera que s'il est allumé et connecté
— ce n'est donc pas vraiment automatique. Le niveau C suppose une VM Windows
dédiée et toujours allumée. L'argument à porter auprès de l'IT n'est pas
technique : le processus actuel dépend d'une seule personne et d'un fichier
local, sans sauvegarde ni traçabilité.

## Le classeur Excel

`scripts/make_template.py` génère `templates/flash_hebdo.xlsx` avec l'onglet
plat, le tableau structuré et un graphique d'exemple. **Les TCD doivent être
ajoutés une fois à la main** (openpyxl ne sait pas les créer) :

1. ouvrir le template dans Excel ;
2. Insertion > Tableau croisé dynamique, source = **le tableau structuré**
   `tbl_donnees` — surtout pas une plage figée du type `A1:J5000`, sinon le TCD
   ne suivra pas la variation du nombre de lignes ;
3. construire les TCD et graphiques ;
4. enregistrer. Le template est ensuite copié tel quel chaque semaine, jamais
   modifié en place.

Si Excel n'est pas pilotable (non installé, boîte de dialogue ouverte, machine
sans Office), l'injection des données est quand même faite et la chaîne bascule
automatiquement sur les graphiques Python : la semaine n'est pas perdue.

## Passer aux graphiques Python

```toml
[publication]
moteur_graphiques = "python"
```

Les graphiques sont alors produits par `publish/charts.py`, sans Office. C'est
la cible à terme : le pipeline devient exécutable sur un serveur, et le
classeur Excel n'est plus qu'une pièce jointe de confort.

## Diffusion

`mail.brouillon = true` crée un brouillon Outlook et l'affiche, sans envoyer.
Le garder à `true` les premiers mois : le coût est nul et cela évite d'envoyer
un flash faux à toute une liste de diffusion. Passer à `false` quand la
confiance est établie.

Si un contrôle bloquant échoue, **rien n'est diffusé** et une alerte part vers
`alertes.destinataires`.

## Surveiller

- `data/_logs/flash.log` — journal détaillé de chaque exécution
- `data/90_sorties/<semaine>/controles_qualite.json` — résultat des contrôles
- `data/90_sorties/<semaine>/echec_*.png` — capture d'écran si le portail a échoué

Code retour de `flash run` : `0` si tout va bien, `1` si les contrôles ont
arrêté la publication. Un planificateur peut s'en servir pour alerter.
