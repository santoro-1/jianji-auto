param(
    [switch]$BuildReleases,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ReleaseDir = Join-Path $ProjectRoot "release"
$ZipPath = Join-Path $ReleaseDir "JianyingAutomationProject-portable.zip"

if ($BuildReleases) {
    $arguments = @{}
    if ($Python) {
        $arguments.Python = $Python
    }
    & (Join-Path $PSScriptRoot "build_all_releases.ps1") @arguments
}

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    $rootFiles = Get-ChildItem -LiteralPath $ProjectRoot -File
    $portableDirectories = @(
        "apps", "data", "docs", "examples", "release", "scripts",
        "src", "tests", "tools", "vendor"
    )
    $nestedFiles = foreach ($directory in $portableDirectories) {
        $path = Join-Path $ProjectRoot $directory
        if (Test-Path -LiteralPath $path -PathType Container) {
            Get-ChildItem -LiteralPath $path -File -Recurse
        }
    }
    $files = @($rootFiles) + @($nestedFiles) | Where-Object {
        $_.FullName -ne $ZipPath -and
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and
        $_.Extension -notin @('.pyc', '.pyo')
    }
    foreach ($file in $files) {
        $entryName = $file.FullName.Substring($ProjectRoot.Length).TrimStart('\', '/') -replace '\\', '/'
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $file.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
    }
} finally {
    $archive.Dispose()
}

Write-Host "Portable project archive: $ZipPath"
