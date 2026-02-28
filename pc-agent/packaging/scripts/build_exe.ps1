Param(
    [string]$PythonExe = "",
    [switch]$Clean
)

# Delegate to Nuitka build script (replaces PyInstaller)
$NuitkaScript = Join-Path $PSScriptRoot "build_exe_nuitka.ps1"

$params = @{}
if ($PythonExe) { $params["PythonExe"] = $PythonExe }
if ($Clean) { $params["Clean"] = $true }

& $NuitkaScript @params
