param(
    [string]$Python = "",
    [switch]$Clean,
    [switch]$UpdateOnly,
    [switch]$WithoutLibraries,
    [switch]$SkipArchive,
    [string]$DigitalHumanServerUrl = "",
    [string]$AsrBundleRoot = "",
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
} elseif ($WithoutLibraries) {
    "JianyingRenderServer-no-libraries-windows-x64.zip"
} elseif ($DeploymentMode -eq "shared") {
    "JianyingRenderServer-shared-windows-x64.zip"
} else {
    "JianyingRenderServer-windows-x64.zip"
}
$ZipPath = Join-Path $ReleaseDir $ZipName
$SpecPath = Join-Path $ProjectRoot "apps\processor\processor_windows.spec"
. (Join-Path $PSScriptRoot "build_helpers.ps1")

if ($DigitalHumanServerUrl) {
    $ParsedDigitalHumanServerUrl = $null
    if (
        -not [Uri]::TryCreate(
            $DigitalHumanServerUrl,
            [UriKind]::Absolute,
            [ref]$ParsedDigitalHumanServerUrl
        ) -or
        $ParsedDigitalHumanServerUrl.Scheme -notin @("http", "https")
    ) {
        throw "DigitalHumanServerUrl must be an absolute HTTP(S) URL."
    }
    $DigitalHumanServerUrl = $DigitalHumanServerUrl.TrimEnd("/")
}
if ($UpdateOnly -and $DigitalHumanServerUrl) {
    throw "UpdateOnly excludes data/processor_config.json; use a full build to set DigitalHumanServerUrl."
}
if ($UpdateOnly -and $WithoutLibraries) {
    throw "UpdateOnly and WithoutLibraries are different delivery modes; choose one."
}
if ($UpdateOnly -and $AsrBundleRoot) {
    throw "UpdateOnly excludes the ASR runtime; install it with a full build."
}

if (-not $Python) {
    $Python = Join-Path $BuildCacheRoot ".collector-build-cpython\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Build Python was not found: $Python`nRun scripts\setup_build_environment.ps1 first, or pass -Python explicitly."
}
& $Python -c "import jwt, cryptography; from cryptography.hazmat.primitives.asymmetric import ec; from jwt.algorithms import ECAlgorithm; assert ECAlgorithm; print('Device authorization build dependencies: OK')"
if ($LASTEXITCODE -ne 0) {
    throw 'Device authorization dependencies are missing; run scripts\setup_build_environment.ps1 before building. No release was created.'
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

    if ($UpdateOnly -and (Test-Path -LiteralPath $DataDir)) {
        $ResolvedDistDir = [System.IO.Path]::GetFullPath($DistDir).TrimEnd('\')
        $ResolvedDataDir = [System.IO.Path]::GetFullPath($DataDir)
        $ExpectedDataPrefix = $ResolvedDistDir + '\'
        if (-not $ResolvedDataDir.StartsWith(
            $ExpectedDataPrefix,
            [System.StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to remove update build data outside dist directory: $ResolvedDataDir"
        }
        # A previous full build can leave data in the reusable dist directory.
        # Code-only updates must never inherit or package that stale data.
        Remove-Item -LiteralPath $ResolvedDataDir -Recurse -Force
    }

    if (-not $UpdateOnly) {
        if (-not $AsrBundleRoot) {
            $AsrBundleRoot = Join-Path $ProjectRoot "vendor\asr_runtime"
        }
        if (Test-Path -LiteralPath $AsrBundleRoot -PathType Container) {
            $AsrPython = Join-Path $AsrBundleRoot "python\python.exe"
            $AsrService = Join-Path $AsrBundleRoot "media_node\asr_service\app.py"
            if (
                -not (Test-Path -LiteralPath $AsrPython -PathType Leaf) -or
                -not (Test-Path -LiteralPath $AsrService -PathType Leaf)
            ) {
                throw "AsrBundleRoot is not a portable ASR runtime: $AsrBundleRoot"
            }
            Write-Host "Copying bundled CPU ASR runtime..." -ForegroundColor Cyan
            Copy-Item -LiteralPath $AsrBundleRoot `
                -Destination (Join-Path $DistDir "asr_runtime") -Recurse -Force
        } else {
            Write-Warning (
                "Portable ASR runtime was not found at $AsrBundleRoot. " +
                "The package can reuse 127.0.0.1:18084, but cannot start ASR itself."
            )
        }
        $LibrarySourceRoot = Join-Path $ProjectRoot "data\libraries"
        if ($WithoutLibraries) {
            Write-Host "Skipping public libraries for first-install code package..." -ForegroundColor Cyan
            foreach ($MaterialPath in @($LibrariesDir, (Join-Path $DataDir "l"))) {
                if (Test-Path -LiteralPath $MaterialPath) {
                    Remove-Item -LiteralPath $MaterialPath -Recurse -Force
                }
            }
            New-Item -ItemType Directory -Path $LibrariesDir -Force | Out-Null
            # The API loads the semantic catalog during startup even when the
            # optional public asset library is delivered separately. Keep a
            # valid empty catalog so a no-library first install can boot.
            $SemanticLibraryDir = Join-Path $LibrariesDir "semantic_visual_library"
            New-Item -ItemType Directory -Path $SemanticLibraryDir -Force | Out-Null
            $EmptySemanticCatalog = [ordered]@{
                schema = "jyd.semantic-visual-catalog.v3"
                library_id = "jyd.semantic-visual-library.default"
                concepts = @()
                assets = @()
            }
            $EmptySemanticCatalog | ConvertTo-Json -Depth 4 | Set-Content `
                -LiteralPath (Join-Path $SemanticLibraryDir "catalog.json") -Encoding UTF8
        } else {
            New-Item -ItemType Directory -Path $LibrariesDir -Force | Out-Null
            foreach ($Name in @(
                "audio_library",
                "effect_library",
                "font_library",
                "sticker_library",
                "corner_sticker_library",
                "semantic_visual_library",
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
        $ProcessorConfig = Get-Content -LiteralPath $ProcessorConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($DigitalHumanServerUrl) {
            $ProcessorConfig.digital_human_server_url = $DigitalHumanServerUrl
        }
        if ($DeploymentMode -eq "shared") {
            $ProcessorConfig.deployment_mode = "shared"
            $ProcessorConfig.host = "0.0.0.0"
            $ProcessorConfig.shared_processor_url = ""
            $ProcessorConfig.auth_authority = "false"
        }
        $ProcessorConfig | ConvertTo-Json | Set-Content -LiteralPath $ProcessorConfigPath -Encoding UTF8
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

    if ($UpdateOnly -and (Test-Path -LiteralPath $DataDir)) {
        throw "UpdateOnly package must not contain a data directory: $DataDir"
    }

    Write-Host "Processor build: $DistDir"
    if ($SkipArchive) {
        Write-Host "Release archive skipped."
    } else {
        $ArchiveArguments = @{
            SourceDirectory = $DistDir
            DestinationPath = $ZipPath
            CompressionLevel = $CompressionLevel
        }
        Write-ReleaseArchive @ArchiveArguments
        Write-Host "Release archive: $ZipPath"
    }
} finally {
    Pop-Location
}
