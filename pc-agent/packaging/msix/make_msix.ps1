Param(
    [Parameter(Mandatory = $true)]
    [string]$IdentityName,

    [Parameter(Mandatory = $true)]
    [string]$Publisher,

    [string]$PublisherDisplayName = "ProgressEye",
    [string]$DisplayName = "ProgressEye",
    [string]$Version = "1.0.0.0",
    [ValidateSet("x64", "x86", "arm64", "neutral")]
    [string]$Architecture = "x64",

    [string]$InputDist = "",
    [string]$OutputPath = "",

    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [switch]$SkipSign
)

$ErrorActionPreference = "Stop"

function New-PlaceholderPng {
    Param(
        [string]$Path,
        [int]$Width,
        [int]$Height,
        [string]$Label
    )

    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap($Width, $Height)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
        $g.Clear([System.Drawing.Color]::FromArgb(15, 15, 26))
        $fontSize = [Math]::Max(8, [Math]::Floor([Math]::Min($Width, $Height) / 6))
        $font = New-Object System.Drawing.Font("Segoe UI", $fontSize, [System.Drawing.FontStyle]::Bold)
        $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(59, 130, 246))
        $format = New-Object System.Drawing.StringFormat
        $format.Alignment = [System.Drawing.StringAlignment]::Center
        $format.LineAlignment = [System.Drawing.StringAlignment]::Center
        $rect = New-Object System.Drawing.RectangleF(0, 0, $Width, $Height)
        $g.DrawString($Label, $font, $brush, $rect, $format)
    }
    finally {
        $g.Dispose()
    }
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

function Ensure-Tool {
    Param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "$Name not found. Install Windows SDK and run from Developer PowerShell."
    }
    return $cmd.Source
}

$PcAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

if (-not $InputDist) {
    $InputDist = Join-Path $PcAgentRoot "dist\ProgressEye"
}
if (-not (Test-Path (Join-Path $InputDist "ProgressEye.exe"))) {
    throw "Input dist not found or invalid: $InputDist"
}

if (-not $OutputPath) {
    $OutputPath = Join-Path $PcAgentRoot ("dist\msix\ProgressEye_{0}_{1}.msix" -f $Version, $Architecture)
}

$makeAppx = Ensure-Tool -Name "makeappx.exe"
$signTool = $null
if (-not $SkipSign -and $PfxPath) {
    $signTool = Ensure-Tool -Name "signtool.exe"
}

$StagingRoot = Join-Path $PcAgentRoot "packaging\msix\_staging"
$AssetsSource = Join-Path $PcAgentRoot "packaging\msix\Assets"
$ManifestTemplate = Join-Path $PcAgentRoot "packaging\msix\AppxManifest.template.xml"
$ManifestPath = Join-Path $StagingRoot "AppxManifest.xml"
$AssetsTarget = Join-Path $StagingRoot "Assets"

if (Test-Path $StagingRoot) {
    Remove-Item $StagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $StagingRoot | Out-Null

Copy-Item (Join-Path $InputDist "*") $StagingRoot -Recurse -Force
New-Item -ItemType Directory -Path $AssetsTarget -Force | Out-Null

$requiredAssets = @(
    @{ Name = "StoreLogo.png"; W = 50; H = 50; Label = "PE" },
    @{ Name = "Square44x44Logo.png"; W = 44; H = 44; Label = "PE" },
    @{ Name = "Square150x150Logo.png"; W = 150; H = 150; Label = "ProgressEye" }
)

foreach ($asset in $requiredAssets) {
    $source = Join-Path $AssetsSource $asset.Name
    $target = Join-Path $AssetsTarget $asset.Name
    if (Test-Path $source) {
        Copy-Item $source $target -Force
    } else {
        New-PlaceholderPng -Path $target -Width $asset.W -Height $asset.H -Label $asset.Label
    }
}

$manifest = Get-Content $ManifestTemplate -Raw
$manifest = $manifest.Replace("__IDENTITY_NAME__", $IdentityName)
$manifest = $manifest.Replace("__PUBLISHER__", $Publisher)
$manifest = $manifest.Replace("__VERSION__", $Version)
$manifest = $manifest.Replace("__ARCH__", $Architecture)
$manifest = $manifest.Replace("__DISPLAY_NAME__", $DisplayName)
$manifest = $manifest.Replace("__PUBLISHER_DISPLAY_NAME__", $PublisherDisplayName)
Set-Content -Path $ManifestPath -Value $manifest -Encoding UTF8

$outputDir = Split-Path $OutputPath -Parent
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

if (Test-Path $OutputPath) {
    Remove-Item $OutputPath -Force
}

& $makeAppx pack /d $StagingRoot /p $OutputPath

if (-not $SkipSign -and $PfxPath) {
    if (-not (Test-Path $PfxPath)) {
        throw "PFX file not found: $PfxPath"
    }
    & $signTool sign /fd SHA256 /f $PfxPath /p $PfxPassword $OutputPath
} else {
    Write-Host "[make_msix] Signing skipped. Use -PfxPath/-PfxPassword for local sideload signing."
}

Write-Host "[make_msix] Done: $OutputPath"
