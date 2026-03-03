Param(
    [string]$PythonExe = "",
    [switch]$Clean,
    [switch]$Fast,
    [switch]$EnableUpx,
    [switch]$SkipBundleVCRuntime,
    [int]$NuitkaJobs = 0,
    [string]$UpxExe = ""
)

# Delegate to Nuitka build script (replaces PyInstaller)
$NuitkaScript = Join-Path $PSScriptRoot "build_exe_nuitka.ps1"

$params = @{}
if ($PythonExe) { $params["PythonExe"] = $PythonExe }
if ($Clean) { $params["Clean"] = $true }
if ($Fast) { $params["Fast"] = $true }
if ($EnableUpx) { $params["EnableUpx"] = $true }
if ($SkipBundleVCRuntime) { $params["SkipBundleVCRuntime"] = $true }
if ($NuitkaJobs -gt 0) { $params["NuitkaJobs"] = $NuitkaJobs }
if ($UpxExe) { $params["UpxExe"] = $UpxExe }

& $NuitkaScript @params
