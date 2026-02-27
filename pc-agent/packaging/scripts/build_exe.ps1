Param(
    [string]$PythonExe = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$PcAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path
$SpecPath = Join-Path $PcAgentRoot "packaging\pyinstaller\progresseye.spec"

if (-not $PythonExe) {
    $venvPython = Join-Path $PcAgentRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $PythonExe = "python"
    }
}

Write-Host "[build_exe] Python: $PythonExe"
Write-Host "[build_exe] Root:   $PcAgentRoot"

Push-Location $PcAgentRoot
try {
    if ($Clean) {
        if (Test-Path (Join-Path $PcAgentRoot "build")) {
            Remove-Item (Join-Path $PcAgentRoot "build") -Recurse -Force
        }
        if (Test-Path (Join-Path $PcAgentRoot "dist")) {
            Remove-Item (Join-Path $PcAgentRoot "dist") -Recurse -Force
        }
    }

    & $PythonExe -m pip install --upgrade pip pyinstaller
    & $PythonExe -m PyInstaller --noconfirm --clean $SpecPath

    $exePath = Join-Path $PcAgentRoot "dist\ProgressEye\ProgressEye.exe"
    if (-not (Test-Path $exePath)) {
        throw "PyInstaller output not found: $exePath"
    }

    Write-Host "[build_exe] Done: $exePath"
}
finally {
    Pop-Location
}
