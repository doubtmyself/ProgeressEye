# ProgressEye PowerShell aliases/functions
# Usage (current session):
#   . C:\ProgressEye\pc-agent\scripts\dev-aliases.ps1

$script:ProgressEyeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$script:PcAgentRoot = Join-Path $script:ProgressEyeRoot "pc-agent"
$script:VenvPython = Join-Path $script:PcAgentRoot "venv\Scripts\python.exe"

function pe-root {
    Set-Location $script:ProgressEyeRoot
}

function pe-pc {
    Set-Location $script:PcAgentRoot
}

function pe-docs {
    Set-Location (Join-Path $script:ProgressEyeRoot "docs")
}

function pe-run {
    if (Test-Path $script:VenvPython) {
        & $script:VenvPython (Join-Path $script:PcAgentRoot "main.py")
        return
    }

    Write-Warning "venv python not found. Trying 'python' from PATH."
    & python (Join-Path $script:PcAgentRoot "main.py")
}

function pe-ocr-setup {
    if (Test-Path $script:VenvPython) {
        & $script:VenvPython (Join-Path $script:PcAgentRoot "setup_tesseract.py")
        return
    }

    Write-Warning "venv python not found. Trying 'python' from PATH."
    & python (Join-Path $script:PcAgentRoot "setup_tesseract.py")
}

function pe-test {
    param(
        [ValidateSet("detection", "downscale", "ocr-accuracy", "ocr-optimize", "all")]
        [string]$Suite = "all"
    )

    $scripts = @()
    switch ($Suite) {
        "detection" { $scripts = @("test_detection.py") }
        "downscale" { $scripts = @("test_downscale.py") }
        "ocr-accuracy" { $scripts = @("test_ocr_accuracy.py") }
        "ocr-optimize" { $scripts = @("test_ocr_optimize.py") }
        default { $scripts = @("test_detection.py", "test_downscale.py", "test_ocr_accuracy.py", "test_ocr_optimize.py") }
    }

    foreach ($scriptName in $scripts) {
        $scriptPath = Join-Path $script:PcAgentRoot $scriptName
        Write-Host ">> Running $scriptName"
        if (Test-Path $script:VenvPython) {
            & $script:VenvPython $scriptPath
        } else {
            & python $scriptPath
        }
    }
}

function pe-exe {
    Push-Location $script:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\scripts\build_exe.ps1"
    } finally {
        Pop-Location
    }
}

function pe-exe-clean {
    Push-Location $script:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\scripts\build_exe.ps1" -Clean
    } finally {
        Pop-Location
    }
}

function pe-exe-fast {
    Push-Location $script:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\scripts\build_exe.ps1" -Fast
    } finally {
        Pop-Location
    }
}

function pe-exe-run {
    $exePath = Join-Path $script:PcAgentRoot "dist\ProgressEye\ProgressEye.exe"
    if (-not (Test-Path $exePath)) {
        Write-Warning "EXE not found: $exePath"
        Write-Host "Run 'pe-exe' (or 'pe-exe-clean') first."
        return
    }

    & $exePath
}

function pe-msix {
    Push-Location $script:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\msix\build_store_msix.ps1" -BuildExe -CleanExe -SkipSign
    } finally {
        Pop-Location
    }
}

function pe-git {
    Push-Location $script:ProgressEyeRoot
    try {
        git @args
    } finally {
        Pop-Location
    }
}

Set-Alias peh Get-Help

# Backward-compatible aliases
Set-Alias pc-root pe-root
Set-Alias pc-agent pe-pc
Set-Alias pc-docs pe-docs
Set-Alias pc-run pe-run
