function Write-ReleaseArchive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDirectory,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath,
        [ValidateSet("Fastest", "Optimal", "NoCompression")]
        [string]$CompressionLevel = "Fastest",
        [string[]]$ExcludeTopLevelNames = @(),
        [int]$ReplaceAttempts = 10
    )

    $TemporaryPath = "$DestinationPath.$([guid]::NewGuid().ToString('N')).tmp.zip"
    try {
        $ArchivePaths = @(
            Get-ChildItem -LiteralPath $SourceDirectory -Force |
                Where-Object { $_.Name -notin $ExcludeTopLevelNames } |
                Select-Object -ExpandProperty FullName
        )
        if (-not $ArchivePaths.Count) {
            throw "No files were selected for archive: $SourceDirectory"
        }
        Compress-Archive `
            -Path $ArchivePaths `
            -DestinationPath $TemporaryPath `
            -CompressionLevel $CompressionLevel `
            -Force

        for ($Attempt = 1; $Attempt -le $ReplaceAttempts; $Attempt++) {
            try {
                if (Test-Path -LiteralPath $DestinationPath -PathType Leaf) {
                    Remove-Item -LiteralPath $DestinationPath -Force
                }
                Move-Item -LiteralPath $TemporaryPath -Destination $DestinationPath -Force
                return
            } catch [System.IO.IOException] {
                if ($Attempt -eq $ReplaceAttempts) {
                    throw
                }
                Start-Sleep -Seconds 2
            }
        }
    } finally {
        if (Test-Path -LiteralPath $TemporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $TemporaryPath -Force -ErrorAction SilentlyContinue
        }
    }
}
