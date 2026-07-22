param(
    [string]$Python = "",
    [switch]$Clean,
    [ValidateSet("Fastest", "Optimal", "NoCompression")]
    [string]$CompressionLevel = "Fastest"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuildCacheRoot = Join-Path (Split-Path -Parent $ProjectRoot) ".jyd-build-cache"
$DistRoot = Join-Path $BuildCacheRoot "dist"
$DistDir = Join-Path $DistRoot "JianyingDraftCollector"
$WorkDir = Join-Path $BuildCacheRoot "pyinstaller\collector"
$ReleaseDir = Join-Path $ProjectRoot "release"
$ZipPath = Join-Path $ReleaseDir "JianyingDraftCollector-windows-x64.zip"
$SpecPath = Join-Path $ProjectRoot "apps\collector\collector_windows.spec"
$Draftc = Join-Path $ProjectRoot "vendor\jy-draftc\jy-draftc.exe"
. (Join-Path $PSScriptRoot "build_helpers.ps1")

if (-not $Python) {
    $Python = Join-Path $BuildCacheRoot ".collector-build-cpython\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Build Python was not found: $Python`nRun scripts\setup_build_environment.ps1 first, or pass -Python explicitly."
}
if (-not (Test-Path -LiteralPath $Draftc -PathType Leaf)) {
    throw "jy-draftc.exe was not found: $Draftc"
}

New-Item -ItemType Directory -Path $DistRoot, $WorkDir, $ReleaseDir -Force | Out-Null
Push-Location $ProjectRoot
try {
    $PyInstallerArguments = @("-m", "PyInstaller", "--noconfirm")
    if ($Clean) {
        $PyInstallerArguments += "--clean"
    }
    $PyInstallerArguments += @("--workpath", $WorkDir, "--distpath", $DistRoot, $SpecPath)
    & $Python @PyInstallerArguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $DistDir -PathType Container)) {
        throw "Build output directory was not found: $DistDir"
    }
    $ReadmeSource = Join-Path $ProjectRoot "docs\LOCAL_COLLECTOR.md"
    Copy-Item -LiteralPath $ReadmeSource -Destination (Join-Path $DistDir "README-COLLECTOR.md") -Force
    Copy-Item -LiteralPath $ReadmeSource -Destination (Join-Path $DistDir "START-HERE.txt") -Force
    Write-ReleaseArchive -SourceDirectory $DistDir -DestinationPath $ZipPath -CompressionLevel $CompressionLevel
    Write-Host "Collector build: $DistDir"
    Write-Host "Release archive: $ZipPath"
} finally {
    Pop-Location
}
