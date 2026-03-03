Param(
    [string]$IdentityFile = "",
    [switch]$BuildExe,
    [switch]$CleanExe,
    [switch]$FastExe,
    [int]$NuitkaJobs = 0,
    [switch]$SkipSign,
    [string]$PfxPath = "",
    [string]$PfxPassword = ""
)

$ErrorActionPreference = "Stop"

$PcAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$BuildExeScript = Join-Path $PcAgentRoot "packaging\scripts\build_exe.ps1"
$MakeMsixScript = Join-Path $PcAgentRoot "packaging\msix\make_msix.ps1"

if (-not $IdentityFile) {
    $IdentityFile = Join-Path $PcAgentRoot "packaging\msix\partner-center.identity.ps1"
}

if (-not (Test-Path $IdentityFile)) {
    throw "Identity file not found: $IdentityFile`nCopy partner-center.identity.ps1.example to partner-center.identity.ps1 and fill real Partner Center values."
}

. $IdentityFile

$required = @("IdentityName", "Publisher", "PublisherDisplayName", "DisplayName", "Version", "Architecture")
foreach ($name in $required) {
    if (-not (Get-Variable -Name $name -Scope Script -ErrorAction SilentlyContinue)) {
        throw "Missing variable in identity file: `$${name}"
    }
}

if ($BuildExe) {
    $buildExeParams = @{
        Clean = $CleanExe
        Fast = $FastExe
    }
    if ($NuitkaJobs -gt 0) {
        $buildExeParams["NuitkaJobs"] = $NuitkaJobs
    }
    & $BuildExeScript @buildExeParams
}

$params = @{
    IdentityName = $IdentityName
    Publisher = $Publisher
    PublisherDisplayName = $PublisherDisplayName
    DisplayName = $DisplayName
    Version = $Version
    Architecture = $Architecture
}

if ($SkipSign) {
    $params["SkipSign"] = $true
} elseif ($PfxPath) {
    $params["PfxPath"] = $PfxPath
    $params["PfxPassword"] = $PfxPassword
} else {
    $params["SkipSign"] = $true
}

& $MakeMsixScript @params
