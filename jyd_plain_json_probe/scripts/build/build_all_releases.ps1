param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$arguments = @{}
if ($Python) {
    $arguments.Python = $Python
}

& (Join-Path $PSScriptRoot "build_collector.ps1") @arguments
& (Join-Path $PSScriptRoot "build_processor.ps1") @arguments
& (Join-Path $PSScriptRoot "build_agent.ps1") @arguments
Write-Host "All Windows release packages are ready in: $ProjectRoot\release"
