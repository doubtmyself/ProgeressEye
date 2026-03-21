Param(
    [string]$IdentityFile = "",
    [switch]$BuildExe,
    [switch]$CleanExe,
    [switch]$FastExe,
    [int]$NuitkaJobs = 0,
    [switch]$SkipSign,
    [string]$PfxPath = "",
    [string]$PfxPassword = "",
    [switch]$EnablePyarmor
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

# Store submission requires MSIX revision (4th part) to be 0.
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Invalid MSIX version format: $Version. Use x.y.z.0 (for example, 1.0.2.0)."
}
$versionParts = $Version.Split(".")
if ([int]$versionParts[3] -ne 0) {
    throw "Invalid MSIX version for Store: $Version. The 4th segment must be 0. Use x.y.z.0 and increment z."
}

if ($BuildExe) {
    $buildExeParams = @{
        Clean = $CleanExe
        Fast = $FastExe
    }
    if ($NuitkaJobs -gt 0) {
        $buildExeParams["NuitkaJobs"] = $NuitkaJobs
    }
    if ($EnablePyarmor) {
        $buildExeParams["EnablePyarmor"] = $true
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
