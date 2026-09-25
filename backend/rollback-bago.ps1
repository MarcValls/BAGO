#Requires -Version 5.1
<#
.SYNOPSIS
  Retired standalone ZIP rollback entrypoint.
.DESCRIPTION
  Runtime restoration is owned by the BAGO ExecutionGateway. Run
  `bago rollback-archive` from an interactive local terminal instead.
#>
[CmdletBinding()]
param(
    [string]$BackupZip = "",
    [string]$InstallDir = "",
    [string]$BackupRoot = "",
    [switch]$RestoreBackedUpState,
    [switch]$SkipTests
)

$command = "bago rollback-archive"
if ($BackupZip) { $command += " --backup-zip `"$BackupZip`"" }
if ($InstallDir) { $command += " --install-dir `"$InstallDir`"" }
if ($BackupRoot) { $command += " --backup-root `"$BackupRoot`"" }
if ($RestoreBackedUpState) { $command += " --restore-backed-up-state" }

Write-Error "Este script ya no restaura directamente. Abre un terminal interactivo y ejecuta: $command"
exit 2
