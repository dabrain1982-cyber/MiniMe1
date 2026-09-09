$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonPath = Join-Path $projectDir '.venv/Scripts/python.exe'
$appPath = Join-Path $projectDir 'streamlit_app.py'
# Browser already opens 8502 at sign-in; start the real everyday balance there.
try {
    $health = Invoke-WebRequest 'http://127.0.0.1:8502/_stcore/health' -UseBasicParsing -TimeoutSec 2
    if ($health.StatusCode -eq 200) { exit }
} catch {}
$env:FINANZBILANZ_DB_PATH = Join-Path $projectDir 'data/finanzbilanz.sqlite3'
Remove-Item Env:FINANZBILANZ_TEST_MODE -ErrorAction SilentlyContinue
Start-Process -FilePath $pythonPath -ArgumentList @('-m', 'streamlit', 'run', ('"' + $appPath + '"'), '--server.port=8502', '--server.address=127.0.0.1', '--server.headless=true') -WorkingDirectory $projectDir -WindowStyle Hidden
