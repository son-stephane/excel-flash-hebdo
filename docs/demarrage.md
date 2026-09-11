# Procédure de démarrage

Document de référence pour la mise en route sur le poste de travail. Il
suppose que **l'environnement virtuel est activé** : l'invite PowerShell est
préfixée de `(.venv)`, et les commandes `python`, `pip`, `pytest` et `flash`
pointent vers cet environnement.

L'activation vaut pour la fenêtre en cours uniquement. À chaque nouvelle
session PowerShell :

```powershell
.venv\Scripts\Activate.ps1
```

En cas de blocage par la politique d'exécution, lever la restriction pour la
seule fenêtre courante — sans droits administrateur, et sans modification
durable du poste :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 1. Vérifier l'installation

```powershell
pytest
```

29 tests verts signifient que Python, les dépendances et le code sont en
place, et que la copie du projet est complète.

```powershell
flash --help
```

Si la commande `flash` est introuvable alors que les tests passent, c'est que
le paquet n'est pas installé : `pip install -e . --no-deps` depuis la racine.

---

## 2. Faire tourner la chaîne à vide

Avant de toucher aux vraies données, vérifier que tout fonctionne sur ce
poste avec des exports factices. Le générateur reproduit les deux
comportements qui comptent : historique complet re-téléchargé à chaque
extraction, et corrections rétroactives d'une semaine à l'autre.

```powershell
flash init
```

```powershell
python scripts\make_sample_data.py --semaines 2026-W36 2026-W37
```

```powershell
flash run --semaine 2026-W36 --sans-extraction --sans-mail --sans-excel
```

```powershell
flash run --semaine 2026-W37 --sans-extraction --sans-mail
```

La deuxième semaine est la plus instructive : elle déclenche la comparaison
N / N-1 et tente de piloter Excel. Inspecter `data\90_sorties\2026-W37\` :
graphiques, `controles_qualite.json`, classeur.

**Point de décision.** Si les TCD se rafraîchissent, le poste est en phase 1
(graphiques Excel). Sinon la chaîne bascule seule sur matplotlib et l'indique
dans le journal — la semaine n'est jamais perdue pour autant.

Effacer ensuite les données de démonstration :

```powershell
Remove-Item -Recurse -Force data\00_raw, data\10_snapshots, data\20_diff, data\30_mart, data\90_sorties
```

---

## 3. Brancher les vrais rapports

**Ne pas commencer par l'automatisation du téléchargement.** Télécharger les
rapports à la main comme d'habitude et les déposer dans `data\inbox\`.

```powershell
flash etat
```

La commande indique quels fichiers sont reconnus. Ajuster le `motif` dans
`config\schemas\*.toml` jusqu'à ce que tous soient trouvés, et renommer
`rapport_a` / `rapport_b` / `rapport_c` en noms parlants.

```powershell
flash ingerer
```

**Le message d'erreur est le guide** : quand le schéma ne correspond pas, il
liste les colonnes attendues *et* celles réellement présentes dans le
fichier. Recopier les vraies dans le TOML, relancer, recommencer.

Sources d'échec les plus fréquentes, dans l'ordre — toutes dans le bloc
`[fichier]` du schéma : encodage (`cp1252` contre `utf-8-sig`), séparateur,
format de date, séparateur décimal.

Renseigner ensuite `[controles]` avec les volumétries réelles, et `[filtre]`
avec la règle appliquée aujourd'hui à la main dans Excel.

```powershell
flash controler
```

---

## 4. Écrire la logique métier

Réécrire `src\flash\transform\sql\mart_flash_hebdo.sql` avec les vraies
colonnes et agrégations. Explorer sans relancer toute la chaîne :

```powershell
flash sql "SELECT * FROM rapport_a LIMIT 20"
```

```powershell
flash mart
```

**Critère de sortie : le mart doit reproduire exactement les chiffres du
flash de la semaine précédente.** Comparer avant d'aller plus loin — si les
chiffres ne coïncident pas maintenant, ils ne coïncideront jamais.

---

## 5. Le classeur Excel

```powershell
python scripts\make_template.py
```

Ouvrir `templates\flash_hebdo.xlsx` dans Excel, ajouter les TCD avec le
**tableau structuré** `tbl_donnees` pour source — jamais une plage figée du
type `A1:J5000`, sinon les TCD ne suivront pas la variation du nombre de
lignes. Enregistrer.

```powershell
flash classeur
```

---

## 6. Le mail

Créer `config\settings.local.toml` (non versionné) avec les vrais
destinataires, l'expéditeur et le chemin SharePoint. Garder
`brouillon = true` : le coût est nul et cela évite d'envoyer un flash faux à
toute une liste de diffusion.

```powershell
flash mail
```

---

## 7. Automatiser le téléchargement

En dernier, parce que c'est la partie la plus fragile — et si elle casse, le
dépôt manuel de l'étape 3 reste le filet de sécurité.

```powershell
playwright install chromium
```

```powershell
playwright codegen https://portail.exemple.interne
```

Reporter les sélecteurs relevés dans `SELECTEURS`, en haut de
`src\flash\extract\portail.py`.

```powershell
python scripts\enregistrer_mot_de_passe.py
```

```powershell
flash extraire
```

---

## 8. Passer la main à l'utilisateur

```powershell
streamlit run app\streamlit_app.py --server.port 8501
```

Vérifier que l'interface répond sur `http://localhost:8501`, puis installer
les tâches planifiées :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\installer_taches.ps1
```

L'utilisateur n'a plus qu'un favori navigateur. Il n'exécute rien.

Ces tâches utilisent le chemin complet de l'interpréteur, et non la commande
`flash` : un planificateur n'exécute pas de script d'activation. Ce n'est pas
une lourdeur, c'est la seule forme qui fonctionne sans session interactive.

---

## Le cycle hebdomadaire, une fois en place

```powershell
flash run
```

Sans argument, la commande traite la semaine courante : téléchargement,
ingestion, contrôles, mart, classeur, graphiques et brouillon de mail. Si un
contrôle bloquant échoue, rien n'est diffusé et une alerte part.

En cas de chiffre suspect, voir [enquete.md](enquete.md).
