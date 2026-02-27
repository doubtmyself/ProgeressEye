Param(
    [string]$PythonExe = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$PcAgentRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\")).Path

if (-not $PythonExe) {
    $venvPython = Join-Path $PcAgentRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        $PythonExe = $venvPython
    } else {
        $PythonExe = "python"
    }
}

Write-Host "[build_exe_nuitka] Python: $PythonExe"
Write-Host "[build_exe_nuitka] Root:   $PcAgentRoot"

Push-Location $PcAgentRoot
try {
    if ($Clean) {
        foreach ($dir in @("build", "dist", "main.build", "main.dist", "main.onefile-build")) {
            $p = Join-Path $PcAgentRoot $dir
            if (Test-Path $p) {
                Write-Host "[build_exe_nuitka] Removing $dir"
                Remove-Item $p -Recurse -Force
            }
        }
    }

    # Install/upgrade Nuitka + ordered-set (improves build performance)
    & $PythonExe -m pip install --upgrade nuitka ordered-set

    # Run Nuitka standalone build
    & $PythonExe -m nuitka `
        --standalone `
        --output-filename=ProgressEye.exe `
        --output-dir=dist `
        --windows-console-mode=disable `
        --windows-icon-from-ico=resources/app-icon.ico `
        --enable-plugin=pyqt6 `
        --include-package=google.auth `
        --include-package=google.oauth2 `
        --include-package=google_auth_oauthlib `
        --include-package-data=google.auth `
        --include-package-data=google_auth_oauthlib `
        --include-data-dir="tesseract=tesseract" `
        --include-data-dir="templates=templates" `
        --include-data-dir="resources=resources" `
        --nofollow-import-to=tkinter `
        --nofollow-import-to=matplotlib `
        --nofollow-import-to=pytest `
        --nofollow-import-to=unittest `
        --nofollow-import-to=test `
        --nofollow-import-to=tests `
        main.py

    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka compilation failed with exit code $LASTEXITCODE"
    }

    # Nuitka outputs to dist/main.dist/ — rename to dist/ProgressEye/ for MSIX compatibility
    $nuitkaOut = Join-Path $PcAgentRoot "dist\main.dist"
    $targetDir = Join-Path $PcAgentRoot "dist\ProgressEye"

    if (Test-Path $targetDir) {
        Remove-Item $targetDir -Recurse -Force
    }

    if (-not (Test-Path $nuitkaOut)) {
        throw "Nuitka output folder not found: $nuitkaOut"
    }

    Rename-Item $nuitkaOut $targetDir

    $exePath = Join-Path $targetDir "ProgressEye.exe"
    if (-not (Test-Path $exePath)) {
        throw "Nuitka output executable not found: $exePath"
    }

    # Clean up Nuitka build artifacts (keep dist/ProgressEye/ only)
    $buildDir = Join-Path $PcAgentRoot "dist\main.build"
    if (Test-Path $buildDir) {
        Remove-Item $buildDir -Recurse -Force
    }

    Write-Host "[build_exe_nuitka] Done: $exePath"
}
finally {
    Pop-Location
}
