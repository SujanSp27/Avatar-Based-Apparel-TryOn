$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
& .venv/Scripts/python.exe scripts/stop_owned.py
if (Test-Path .runtime/pgsql/bin/pg_ctl.exe) { & .runtime/pgsql/bin/pg_ctl.exe -D .runtime/pgdata stop -m fast }
