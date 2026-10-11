param([ValidateSet('cpu','cuda')][string]$Torch = 'cpu')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not (Test-Path .venv/Scripts/python.exe)) { py -3.12 -m venv .venv }
if (-not (Test-Path .venv/Scripts/python.exe)) { throw 'Python 3.12 virtual environment creation failed.' }
& .venv/Scripts/python.exe -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($Torch -eq 'cuda') {
    & .venv/Scripts/python.exe -m pip install --no-cache-dir -r requirements-torch-cuda.txt
    if ($LASTEXITCODE -ne 0) { throw 'CUDA dependency installation failed.' }
}
& .venv/Scripts/python.exe scripts/download_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Model/sample asset download failed.' }
& .venv/Scripts/python.exe scripts/create_demo_garment.py
if ($LASTEXITCODE -ne 0) { throw 'Demo garment creation failed.' }
if (-not (Test-Path .runtime/pgsql/bin/pg_ctl.exe)) {
    & .venv/Scripts/python.exe scripts/download_postgres.py
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL download failed.' }
}
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
if (-not (Test-Path .runtime/pgdata/PG_VERSION)) {
    Set-Content .runtime/pg-password.txt -Value 'tryon_local_only' -Encoding ascii
    & .runtime/pgsql/bin/initdb.exe -D .runtime/pgdata -U tryon -A scram-sha-256 --pwfile=.runtime/pg-password.txt -E UTF8 --locale=C
    if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
}
Push-Location frontend
try { npm.cmd ci --no-audit --no-fund } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed.' }
& "$PSScriptRoot/start-postgres.ps1"
& .venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
