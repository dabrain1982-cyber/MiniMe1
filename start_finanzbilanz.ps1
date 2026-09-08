$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectDir ".venv\Scripts\python.exe"
$appPath = Join-Path $projectDir "streamlit_app.py"
$url = "http://localhost:8501"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Die lokale Python-Umgebung fehlt. Bitte zuerst die Pakete aus requirements.txt installieren."
}

$listener = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if (-not $listener) {
    Start-Process -FilePath $pythonPath `
        -ArgumentList @("-m", "streamlit", "run", $appPath, "--server.port=8501") `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $response = Invoke-WebRequest -Uri "$url/_stcore/health" -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # Die App startet noch.
        }
    }
    if (-not $ready) {
        throw "Die Finanzbilanz ist nicht innerhalb von 15 Sekunden gestartet."
    }
}

Start-Process $url
Write-Host "Finanzbilanz läuft unter $url"
