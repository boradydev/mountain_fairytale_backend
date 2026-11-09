param(
    [ValidateSet('init','start','stop','check','migrate','reset','seed','seed-status','verify','benchmark','report')]
    [string]$Action = 'check',
    [ValidateSet('main','high')][string]$Profile = 'main',
    [int]$Seed = 20261110,
    [int]$BatchSize = 25,
    [double]$Rate = 5,
    [int]$Requests = 10,
    [ValidateRange(1,4)][int]$Concurrency = 1,
    [string]$Confirm,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $root
try {
    if ($Help) {
        & ./.venv/Scripts/python.exe -m scripts.load.manage --help
        Write-Host 'Examples: .\scripts\load\load.ps1 init -Confirm mountain_fairytale_load'
        Write-Host '.\scripts\load\load.ps1 seed -Profile main -Rate 5 -BatchSize 25'
        Write-Host '.\scripts\load\load.ps1 benchmark -Requests 20 -Concurrency 2'
        return
    }
    if ($Action -eq 'stop') {
        $statePath = Join-Path $root '.codex-tmp/load/process.json'
        if (!(Test-Path -LiteralPath $statePath)) { throw 'No managed load process state.' }
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if (!$process) { throw 'Load process absent; inspect stale state manually.' }
        $expectedExecutable = & ./.venv/Scripts/python.exe -c 'import sys; print(sys._base_executable)'
        if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.created -or
            $process.Path -ne $expectedExecutable) { throw 'Process identity mismatch; refusing stop.' }
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8002/health/ready' -TimeoutSec 5
        if ($response.Headers['X-Load-Run'] -ne $state.run_id) { throw 'Load run attestation mismatch.' }
        $listeners = @(Get-NetTCPConnection -LocalPort 8002 -State Listen -ErrorAction Stop)
        if (!$listeners -or @($listeners | Where-Object { $_.OwningProcess -ne $state.pid }).Count) {
            throw 'Port 8002 owner mismatch; refusing stop.'
        }
        Stop-Process -Id $state.pid
        Remove-Item -LiteralPath $statePath
    } else {
        $command = if ($Action -eq 'start') { 'serve' } else { $Action }
        $commandArgs = @($command, '--profile', $Profile, '--seed', $Seed, '--batch-size', $BatchSize,
                         '--rate', $Rate.ToString([System.Globalization.CultureInfo]::InvariantCulture),
                         '--requests', $Requests, '--concurrency', $Concurrency)
        if ($Confirm) { $commandArgs += @('--confirm', $Confirm) }
        & ./.venv/Scripts/python.exe -m scripts.load.manage @commandArgs
        if ($LASTEXITCODE -ne 0) { throw "Load command failed ($LASTEXITCODE)" }
    }
} finally { Pop-Location }
