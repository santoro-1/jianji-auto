param(
    [string]$Python = "",
    [switch]$Clean,
    [switch]$UpdateOnly,
    [ValidateSet("standalone", "shared")]
    [string]$DeploymentMode = "standalone",
    [ValidateSet("Fastest", "Optimal", "NoCompression")]
    [string]$CompressionLevel = "Fastest"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$BuildCacheRoot = Join-Path (Split-Path -Parent $ProjectRoot) ".jyd-build-cache"
$DistRoot = Join-Path $BuildCacheRoot "dist"
$DistDir = Join-Path $DistRoot "JianyingRenderServer"
$WorkDir = Join-Path $BuildCacheRoot "pyinstaller\processor"
$DataDir = Join-Path $DistDir "data"
$LibrariesDir = Join-Path $DataDir "libraries"
$ReleaseDir = Join-Path $ProjectRoot "release"
$ZipName = if ($UpdateOnly) {
    "JianyingRenderServer-update-windows-x64.zip"
} elseif ($DeploymentMode -eq "shared") {
    "JianyingRenderServer-shared-windows-x64.zip"
} else {
    "JianyingRenderServer-windows-x64.zip"
}
$ZipPath = Join-Path $ReleaseDir $ZipName
$SpecPath = Join-Path $ProjectRoot "apps\processor\processor_windows.spec"
. (Join-Path $PSScriptRoot "build_helpers.ps1")

if (-not $Python) {
    $Python = Join-Path $BuildCacheRoot ".collector-build-cpython\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Build Python was not found: $Python`nRun scripts\setup_build_environment.ps1 first, or pass -Python explicitly."
}

$DraftcRoot = Join-Path $ProjectRoot "vendor\jy-draftc"
$Draftc = Join-Path $DraftcRoot "jy-draftc.exe"
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

    if (-not $UpdateOnly) {
        New-Item -ItemType Directory -Path $LibrariesDir -Force | Out-Null
        $LibrarySourceRoot = Join-Path $ProjectRoot "data\libraries"
        foreach ($Name in @(
            "audio_library",
            "effect_library",
            "font_library",
            "sticker_library",
            "corner_sticker_library",
            "text_effect_library",
            "text_style_library"
        )) {
            $Source = Join-Path $LibrarySourceRoot $Name
            if (Test-Path -LiteralPath $Source -PathType Container) {
                Copy-Item -LiteralPath $Source -Destination $LibrariesDir -Recurse -Force
            }
        }

        $TextTemplateSource = Join-Path $LibrarySourceRoot "text_template_library"
        if (Test-Path -LiteralPath $TextTemplateSource -PathType Container) {
            $CompactLibraryParent = Join-Path $DataDir "l"
            New-Item -ItemType Directory -Path $CompactLibraryParent -Force | Out-Null
            Copy-Item -LiteralPath $TextTemplateSource -Destination (Join-Path $CompactLibraryParent "t") -Recurse -Force
        }

        $TemplateSource = Join-Path $ProjectRoot "data\template_library"
        if (Test-Path -LiteralPath $TemplateSource -PathType Container) {
            Copy-Item -LiteralPath $TemplateSource -Destination $DataDir -Recurse -Force
        } else {
            New-Item -ItemType Directory -Path (Join-Path $DataDir "template_library") -Force | Out-Null
        }

        $StorageDir = Join-Path $DataDir "web_storage"
        New-Item -ItemType Directory -Path $StorageDir -Force | Out-Null
        $AssetAdmin = Join-Path $ProjectRoot "data\web_storage\asset_admin.json"
        if (Test-Path -LiteralPath $AssetAdmin -PathType Leaf) {
            Copy-Item -LiteralPath $AssetAdmin -Destination $StorageDir -Force
        }
        $ProcessorConfigPath = Join-Path $DataDir "processor_config.json"
        Copy-Item -LiteralPath (Join-Path $ProjectRoot "apps\processor\processor_config.example.json") -Destination $ProcessorConfigPath -Force
        if ($DeploymentMode -eq "shared") {
            $ProcessorConfig = Get-Content -LiteralPath $ProcessorConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
            $ProcessorConfig.deployment_mode = "shared"
            $ProcessorConfig.host = "0.0.0.0"
            $ProcessorConfig.digital_human_server_url = "http://127.0.0.1:8000"
            $ProcessorConfig.shared_processor_url = ""
            $ProcessorConfig.auth_authority = "false"
            $ProcessorConfig | ConvertTo-Json | Set-Content -LiteralPath $ProcessorConfigPath -Encoding UTF8
        }
    }

    $ToolsDir = Join-Path $DistDir "tools"
    New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
    Copy-Item -LiteralPath $Draftc -Destination (Join-Path $ToolsDir "jy-draftc.exe") -Force
    $DraftcLicense = Join-Path $DraftcRoot "LICENSE"
    if (Test-Path -LiteralPath $DraftcLicense -PathType Leaf) {
        Copy-Item -LiteralPath $DraftcLicense -Destination $ToolsDir -Force
    }
    $ReadmeSource = if ($UpdateOnly) {
        Join-Path $ProjectRoot "docs\PROCESSOR_UPDATE.md"
    } elseif ($DeploymentMode -eq "shared") {
        Join-Path $ProjectRoot "docs\SHARED_PROCESSOR_QUICK_START.md"
    } else {
        Join-Path $ProjectRoot "docs\PROCESSOR_DEPLOYMENT.md"
    }
    Copy-Item -LiteralPath $ReadmeSource -Destination (Join-Path $DistDir "README-PROCESSOR.md") -Force
    Copy-Item -LiteralPath $ReadmeSource -Destination (Join-Path $DistDir "START-HERE.txt") -Force

    $ArchiveArguments = @{
        SourceDirectory = $DistDir
        DestinationPath = $ZipPath
        CompressionLevel = $CompressionLevel
    }
    if ($UpdateOnly) {
        $ArchiveArguments.ExcludeTopLevelNames = @("data")
    }
    Write-ReleaseArchive @ArchiveArguments
    Write-Host "Processor build: $DistDir"
    Write-Host "Release archive: $ZipPath"
} finally {
    Pop-Location
}
