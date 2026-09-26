[CmdletBinding()]
param(
    [Alias("install-dir")]
    [string]$InstallDir = "",
    [Alias("purge-state")]
    [switch]$PurgeState
)

$ErrorActionPreference = "Stop"
throw "La desinstalación directa está deshabilitada. Usa el Manager BAGO para autorizar system.install.uninstall mediante ExecutionGateway."
