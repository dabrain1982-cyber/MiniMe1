$ErrorActionPreference = 'Stop'
$markProject = Join-Path $PSScriptRoot 'mark_makler'
$markPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $markPython)) { throw 'Die lokale Python-Umgebung fehlt.' }
Push-Location -LiteralPath $markProject
try {
    & $markPython -m streamlit run app.py --server.address 127.0.0.1 --server.port 8503 --server.headless true
} finally {
    Pop-Location
}
