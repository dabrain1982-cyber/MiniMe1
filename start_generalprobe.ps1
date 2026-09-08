$env:FINANZBILANZ_DB_PATH = Join-Path $PSScriptRoot 'data/generalprobe-20260906.sqlite3'
$env:FINANZBILANZ_TEST_MODE = '1'
try {
    & "$PSScriptRoot/.venv/Scripts/python.exe" -m streamlit run "$PSScriptRoot/streamlit_app.py" --server.port=8502 --server.address=127.0.0.1
} finally {
    Remove-Item Env:FINANZBILANZ_DB_PATH -ErrorAction SilentlyContinue
    Remove-Item Env:FINANZBILANZ_TEST_MODE -ErrorAction SilentlyContinue
}
