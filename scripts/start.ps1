param([switch]$SkipDatabase)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
if (-not $SkipDatabase) { & "$PSScriptRoot/start-postgres.ps1" }
& .venv/Scripts/python.exe -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
& .venv/Scripts/python.exe scripts/start_mongodb.py
if ($LASTEXITCODE -ne 0) { throw 'Measurement MongoDB startup failed.' }
$runtimePath = Join-Path $projectRoot '.runtime'
New-Item -ItemType Directory -Force -Path $runtimePath | Out-Null
$pythonExe = Join-Path $projectRoot '.venv/Scripts/python.exe'
$viteScript = Join-Path $projectRoot 'frontend/node_modules/vite/bin/vite.js'
foreach ($portNumber in @(8000,5173)) {
    $socket = New-Object System.Net.Sockets.TcpClient
    try { $socket.Connect('127.0.0.1', $portNumber); throw "Port $portNumber is already in use. Stop this project's earlier instance first." }
    catch [System.Net.Sockets.SocketException] { }
    finally { $socket.Dispose() }
}
$api = Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput "$runtimePath/backend.log" -RedirectStandardError "$runtimePath/backend-error.log" -PassThru
$viteArguments = '"{0}" --host 127.0.0.1 --port 5173 --strictPort' -f $viteScript
$web = Start-Process -FilePath 'node' -ArgumentList $viteArguments -WorkingDirectory "$projectRoot/frontend" -WindowStyle Hidden -RedirectStandardOutput "$runtimePath/frontend.log" -RedirectStandardError "$runtimePath/frontend-error.log" -PassThru
@{backend=@{pid=$api.Id; startedUtc=$api.StartTime.ToUniversalTime().ToString('o')}; frontend=@{pid=$web.Id; startedUtc=$web.StartTime.ToUniversalTime().ToString('o')}} | ConvertTo-Json | Set-Content "$runtimePath/processes.json"
$ready = $false
for ($attempt=0; $attempt -lt 40; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $page = Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 2
        if ($health.status -eq 'ok' -and $page.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'App did not become ready. Inspect .runtime/backend-error.log and frontend-error.log.' }
Write-Output 'Frontend: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs'
