param([ValidateSet('start','stop','check','migrate','reset','admin-password','init','seed','seed-status','manual-phones')][string]$Action = 'check')
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $root
try {
    if ($Action -eq 'stop') {
        $statePath = Join-Path $root '.codex-tmp/qa-process.json'
        if (!(Test-Path -LiteralPath $statePath)) { throw 'No managed QA process state.' }
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        $process = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
        if (!$process) { Remove-Item -LiteralPath $statePath; Write-Host 'QA process already stopped.'; return }
        $expectedExecutable = & ./.venv/Scripts/python.exe -c 'import sys; print(sys._base_executable)'
        if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $state.created -or
            $process.Path -ne $expectedExecutable) {
            throw 'Process identity mismatch; refusing to stop.'
        }
        $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8001/health/ready' -TimeoutSec 5
        if ($response.Headers['X-QA-Run'] -ne $state.run_id) { throw 'QA run attestation mismatch; refusing to stop.' }
        Stop-Process -Id $state.pid
        Remove-Item -LiteralPath $statePath -ErrorAction SilentlyContinue
        Write-Host 'Stopped only managed QA backend.'
    } else {
        $command = if ($Action -eq 'start') { 'serve' } else { $Action }
        & ./.venv/Scripts/python.exe -m scripts.qa.manage $command
        if ($LASTEXITCODE -ne 0) { throw "QA command failed ($LASTEXITCODE)" }
    }
} finally { Pop-Location }
