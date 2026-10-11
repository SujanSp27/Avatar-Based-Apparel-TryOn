$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
$server = Join-Path $projectRoot '.runtime/pgsql/bin/pg_ctl.exe'
if (-not (Test-Path -LiteralPath $server)) { throw 'Run scripts/download_postgres.py first.' }
& $server -D .runtime/pgdata status 2>$null
if ($LASTEXITCODE -ne 0) {
    $process = Start-Process -FilePath $server -ArgumentList '-D .runtime/pgdata -l .runtime/postgres.log -o "-p 5433 -h 127.0.0.1" start -w' -WindowStyle Hidden -PassThru
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw 'PostgreSQL failed; see .runtime/postgres.log' }
}
$env:PGPASSWORD = 'tryon_local_only'
$exists = & .runtime/pgsql/bin/psql.exe -h 127.0.0.1 -p 5433 -U tryon -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='tryon'"
if ($exists -ne '1') { & .runtime/pgsql/bin/createdb.exe -h 127.0.0.1 -p 5433 -U tryon tryon }
Remove-Item Env:PGPASSWORD
