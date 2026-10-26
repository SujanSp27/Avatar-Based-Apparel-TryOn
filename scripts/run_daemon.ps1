param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot
& "$PSScriptRoot/start.ps1"
$runtimeJson = Join-Path $projectRoot '.runtime/processes.json'
$p = Get-Content $runtimeJson | ConvertFrom-Json
Wait-Process -Id @($p.backend.pid, $p.frontend.pid)
