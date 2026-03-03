Param(
    [string]$PythonExe = "",
    [switch]$Clean,
    [switch]$EnableUpx,
    [switch]$SkipBundleVCRuntime,
    [string]$UpxExe = ""
)

# Delegate to Nuitka build script (replaces PyInstaller)
$NuitkaScript = Join-Path $PSScriptRoot "build_exe_nuitka.ps1"

$params = @{}
if ($PythonExe) { $params["PythonExe"] = $PythonExe }
if ($Clean) { $params["Clean"] = $true }
if ($EnableUpx) { $params["EnableUpx"] = $true }
if ($SkipBundleVCRuntime) { $params["SkipBundleVCRuntime"] = $true }
if ($UpxExe) { $params["UpxExe"] = $UpxExe }

& $NuitkaScript @params
