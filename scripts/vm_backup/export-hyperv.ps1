#Requires -Version 5.1
#Requires -RunAsAdministrator

<#
.SYNOPSIS
Exports a Hyper-V VM at most once per interval and retains recent exports.
.EXAMPLE
powershell.exe -NoProfile -File .\export-hyperv.ps1 -VMName "MyVM" -BackupRoot "E:\VM-Backups"
.NOTES
Running VMs default to crash-consistent capture (no guest filesystem freeze).
Data-consistent capture is optional and requires working guest integration.
No automatic fallback is performed. Powered-off VMs are also supported.
Only this script's completed exports for this VM are eligible for retention.
Failed exports retain a .partial suffix and are not removed automatically.
#>
[CmdletBinding()]
param(
    [ValidateNotNullOrEmpty()]
    [string]$VMName = 'ubuntu_server',

    [ValidateNotNullOrEmpty()]
    [string]$BackupRoot = 'E:\vm_backup\mountain_fairytale',

    [ValidateRange(1, 3650)]
    [int]$IntervalDays = 7,

    [ValidateRange(1, 1000)]
    [int]$KeepCopies = 3,

    [ValidateSet('CaptureCrashConsistentState', 'CaptureDataConsistentState')]
    [string]$CaptureLiveState = 'CaptureCrashConsistentState'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$lockStream = $null
$logPath = $null
$exitCode = 1

function Write-BackupLog {
    param([string]$Message)
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    if ($logPath) {
        Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
    }
}

function Get-CompletedExports {
    param([string]$Root, [guid]$VMId)
    foreach ($directory in Get-ChildItem -LiteralPath $Root -Directory) {
        $pattern = '^{0}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{2}}-\d{{2}}-\d{{2}}_[0-9a-f]{{8}}$' -f $VMId
        if ($directory.Name -notmatch $pattern -or
            ($directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { continue }
        $marker = Join-Path $directory.FullName 'ExportCompleted.json'
        if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { continue }
        try {
            $metadata = Get-Content -LiteralPath $marker -Raw | ConvertFrom-Json
            if ($metadata.Format -ne 'HyperVExport-v1' -or $metadata.VMId -ne [string]$VMId) { continue }
            [pscustomobject]@{
                Path = $directory.FullName
                CompletedUtc = [datetimeoffset]::Parse($metadata.CompletedUtc).UtcDateTime
            }
        }
        catch { Write-Warning "Ignoring invalid completion marker: $marker" }
    }
}

try {
    Import-Module Hyper-V -ErrorAction Stop

    # A missing drive fails here; directories are created only at the given path.
    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
    }
    $rootItem = Get-Item -LiteralPath $BackupRoot -ErrorAction Stop
    if (-not $rootItem.PSIsContainer -or $rootItem.PSProvider.Name -ne 'FileSystem') {
        throw 'BackupRoot must be an existing filesystem directory.'
    }
    $root = $rootItem.FullName

    # Exclusive handle prevents overlapping runs using this backup directory.
    $lockPath = Join-Path $root '.hyperv-export.lock'
    try {
        $lockStream = [System.IO.File]::Open(
            $lockPath,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    }
    catch {
        throw "Cannot lock backup directory (another export may be running): $($_.Exception.Message)"
    }

    $vm = Get-VM -Name $VMName -ErrorAction Stop
    if (@($vm).Count -ne 1 -or $vm.Name -ne $VMName) {
        throw 'VMName must identify exactly one VM by its full name.'
    }
    $logPath = Join-Path $root 'backup.log'
    $completed = @(Get-CompletedExports -Root $root -VMId $vm.Id |
        Sort-Object CompletedUtc -Descending)
    if ($completed.Count -gt 0 -and
        [datetime]::UtcNow -lt $completed[0].CompletedUtc.AddDays($IntervalDays)) {
        Write-BackupLog "SKIPPED: last successful export is less than $IntervalDays days old."
        exit 0
    }
    $state = [string]$vm.State
    if ($state -notin @('Running', 'Off')) {
        throw "VM must be Running or Off; current state: $state"
    }

    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $token = [guid]::NewGuid().ToString('N').Substring(0, 8)
    $exportName = '{0}_{1}_{2}' -f $vm.Id, $stamp, $token
    $partialPath = Join-Path $root ($exportName + '.partial')
    $finalPath = Join-Path $root $exportName
    New-Item -ItemType Directory -Path $partialPath | Out-Null

    Write-BackupLog "Starting export: VM=$($vm.Name); state=$state; capture=$CaptureLiveState; destination=$partialPath"
    $exportParameters = @{
        VM = $vm
        Path = $partialPath
        ErrorAction = 'Stop'
    }
    if ($state -eq 'Running') {
        $exportParameters.CaptureLiveState = $CaptureLiveState
    }

    # Synchronous call: mark complete only after Export-VM returns successfully.
    Export-VM @exportParameters
    @{
        Format = 'HyperVExport-v1'
        VMId = [string]$vm.Id
        VMName = $vm.Name
        CaptureLiveState = $(if ($state -eq 'Running') { $CaptureLiveState } else { 'Off' })
        CompletedUtc = [datetime]::UtcNow.ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $partialPath 'ExportCompleted.json') -Encoding UTF8
    Rename-Item -LiteralPath $partialPath -NewName $exportName
    Write-BackupLog "SUCCESS: $finalPath"

    $obsolete = @(Get-CompletedExports -Root $root -VMId $vm.Id |
        Sort-Object CompletedUtc -Descending | Select-Object -Skip $KeepCopies)
    foreach ($copy in $obsolete) {
        # Verify the absolute deletion target is a direct child of this root.
        $target = [System.IO.Path]::GetFullPath($copy.Path)
        $parent = [System.IO.Path]::GetDirectoryName($target)
        if ($parent.TrimEnd('\') -ne $root.TrimEnd('\')) {
            throw "Refusing to remove a directory outside BackupRoot: $target"
        }
        Remove-Item -LiteralPath $target -Recurse -Force
        Write-BackupLog "REMOVED old export: $target"
    }
    $exitCode = 0
}
catch {
    $failure = $_.Exception.Message
    try { Write-BackupLog "FAILED: $failure" } catch { Write-Warning $failure }
    Write-Error -Message $failure -ErrorAction Continue
}
finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
}

exit $exitCode
