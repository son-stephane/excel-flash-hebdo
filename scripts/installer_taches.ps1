<#
    Installe les taches planifiees Windows du flash hebdomadaire.

    A lancer UNE FOIS, depuis un PowerShell ouvert dans le dossier du projet :
        powershell -ExecutionPolicy Bypass -File scripts\installer_taches.ps1

    Deux taches sont creees :

      "Flash hebdo - interface"  a l'ouverture de session, demarre Streamlit
                                 en arriere-plan. L'utilisateur n'a plus qu'un
                                 favori navigateur vers http://localhost:8501 :
                                 il n'execute rien lui-meme.

      "Flash hebdo - traitement" chaque lundi matin, prepare le flash sans le
                                 diffuser. Desactivee par defaut : l'activer
                                 quand la chaine tourne de facon fiable.

    Ces taches s'executent sous la session de l'utilisateur : la machine doit
    etre allumee et la session ouverte. Pour un fonctionnement reellement
    autonome, installer le projet sur une VM toujours allumee et reprendre ce
    meme script avec un compte de service.
#>

param(
    [string]$Projet = (Resolve-Path "$PSScriptRoot\.."),
    [int]$Port = 8501,
    [string]$JourTraitement = "Monday",
    [string]$HeureTraitement = "07:00",
    [switch]$ActiverTraitement
)

$ErrorActionPreference = "Stop"

$python = Join-Path $Projet ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $python)) {
    Write-Error "Environnement Python introuvable : $python`nCreer d'abord l'environnement (voir README)."
}

# --- Interface Streamlit, au demarrage de session ------------------------
$actionInterface = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "-m streamlit run app\streamlit_app.py --server.port $Port --server.headless true" `
    -WorkingDirectory $Projet

$declencheurInterface = New-ScheduledTaskTrigger -AtLogOn
$reglages = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName "Flash hebdo - interface" `
    -Action $actionInterface -Trigger $declencheurInterface -Settings $reglages `
    -Description "Demarre l'interface du flash hebdomadaire sur http://localhost:$Port" `
    -Force | Out-Null
Write-Host "Tache 'Flash hebdo - interface' installee (http://localhost:$Port)"

# --- Traitement hebdomadaire --------------------------------------------
$actionTraitement = New-ScheduledTaskAction `
    -Execute (Join-Path $Projet ".venv\Scripts\python.exe") `
    -Argument "-m flash run --sans-mail" `
    -WorkingDirectory $Projet

$declencheurTraitement = New-ScheduledTaskTrigger -Weekly `
    -DaysOfWeek $JourTraitement -At $HeureTraitement

Register-ScheduledTask -TaskName "Flash hebdo - traitement" `
    -Action $actionTraitement -Trigger $declencheurTraitement -Settings $reglages `
    -Description "Prepare le flash hebdomadaire (sans diffusion)" `
    -Force | Out-Null

if (-not $ActiverTraitement) {
    Disable-ScheduledTask -TaskName "Flash hebdo - traitement" | Out-Null
    Write-Host "Tache 'Flash hebdo - traitement' installee mais DESACTIVEE."
    Write-Host "  L'activer avec : Enable-ScheduledTask -TaskName 'Flash hebdo - traitement'"
} else {
    Write-Host "Tache 'Flash hebdo - traitement' installee et activee ($JourTraitement $HeureTraitement)."
}

Write-Host ""
Write-Host "Creer un favori navigateur vers http://localhost:$Port et le donner a l'utilisateur."
