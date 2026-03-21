# ProgressEye PowerShell aliases/functions
# Usage (current session):
#   . C:\ProgressEye\pc-agent\scripts\dev-aliases.ps1

$global:ProgressEyeRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$global:PcAgentRoot = Join-Path $global:ProgressEyeRoot "pc-agent"
$global:VenvPython = Join-Path $global:PcAgentRoot "venv\Scripts\python.exe"

function pe-root {
    Set-Location $global:ProgressEyeRoot
}

function pe-pc {
    Set-Location $global:PcAgentRoot
}

function pe-docs {
    Set-Location (Join-Path $global:ProgressEyeRoot "docs")
}

function pe-run {
    param(
        [switch]$d
    )
    $mainPy = Join-Path $global:PcAgentRoot "main.py"
    $extraArgs = @()
    if ($d) { $extraArgs += "-d" }

    if (Test-Path $global:VenvPython) {
        & $global:VenvPython $mainPy @extraArgs
        return
    }

    Write-Warning "venv python not found. Trying 'python' from PATH."
    & python $mainPy @extraArgs
}

function pe-ocr-setup {
    if (Test-Path $global:VenvPython) {
        & $global:VenvPython (Join-Path $global:PcAgentRoot "setup_tesseract.py")
        return
    }

    Write-Warning "venv python not found. Trying 'python' from PATH."
    & python (Join-Path $global:PcAgentRoot "setup_tesseract.py")
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
        $scriptPath = Join-Path $global:PcAgentRoot $scriptName
        Write-Host ">> Running $scriptName"
        if (Test-Path $global:VenvPython) {
            & $global:VenvPython $scriptPath
        } else {
            & python $scriptPath
        }
    }
}

function pe-kill {
    $killed = $false

    foreach ($name in @("ProgressEye", "main")) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            try {
                Stop-Process -Id $p.Id -Force -ErrorAction Stop
                Write-Host "Stopped: $($p.ProcessName) (PID=$($p.Id))"
                $killed = $true
            } catch {
            }
        }
    }

    # Fallback: taskkill can terminate process trees that Stop-Process may miss.
    # Ignore "not found" case and silence taskkill output.
    foreach ($image in @("ProgressEye.exe", "main.exe")) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "taskkill /F /T /IM $image >nul 2>&1" -NoNewWindow -Wait -ErrorAction SilentlyContinue | Out-Null
    }

    if ($killed) {
        Start-Sleep -Milliseconds 700
    }
}

function pe-exe {
    Push-Location $global:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\scripts\build_exe.ps1" -Fast -NuitkaJobs 0 -EnablePyarmor
    } finally {
        Pop-Location
    }
}

function pe-exe-clean {
    Push-Location $global:PcAgentRoot
    try {
        pe-kill
        powershell -ExecutionPolicy Bypass -File ".\packaging\scripts\build_exe.ps1" -Clean -Fast -NuitkaJobs 0 -EnablePyarmor
    } finally {
        Pop-Location
    }
}

function pe-exe-run {
    $exePath = Join-Path $global:PcAgentRoot "dist\ProgressEye\ProgressEye.exe"
    if (-not (Test-Path $exePath)) {
        Write-Warning "EXE not found: $exePath"
        Write-Host "Run 'pe-exe' (or 'pe-exe-clean') first."
        return
    }

    & $exePath
}

function pe-msix {
    Push-Location $global:PcAgentRoot
    try {
        powershell -ExecutionPolicy Bypass -File ".\packaging\msix\build_store_msix.ps1" -BuildExe -FastExe -NuitkaJobs 0 -SkipSign -EnablePyarmor
    } finally {
        Pop-Location
    }
}

function pe-msix-clean {
    Push-Location $global:PcAgentRoot
    try {
        pe-kill
        powershell -ExecutionPolicy Bypass -File ".\packaging\msix\build_store_msix.ps1" -BuildExe -CleanExe -FastExe -NuitkaJobs 0 -SkipSign -EnablePyarmor
    } finally {
        Pop-Location
    }
}

function pe-git {
    Push-Location $global:ProgressEyeRoot
    try {
        git @args
    } finally {
        Pop-Location
    }
}

Set-Alias -Scope Global peh Get-Help

# Backward-compatible aliases
Set-Alias -Scope Global pc-root pe-root
Set-Alias -Scope Global pc-agent pe-pc
Set-Alias -Scope Global pc-docs pe-docs
Set-Alias -Scope Global pc-run pe-run

# Ensure commands remain available even when this script is invoked with '&'
# (child scope execution). Copy functions to global scope explicitly.
$script:_peFunctions = @(
    "pe-root",
    "pe-pc",
    "pe-docs",
    "pe-run",
    "pe-ocr-setup",
    "pe-test",
    "pe-kill",
    "pe-exe",
    "pe-exe-clean",
    "pe-exe-run",
    "pe-msix",
    "pe-msix-clean",
    "pe-git"
)

foreach ($fn in $script:_peFunctions) {
    $localDef = Get-Item -Path ("function:" + $fn) -ErrorAction SilentlyContinue
    if ($null -ne $localDef) {
        Set-Item -Path ("function:global:" + $fn) -Value $localDef.ScriptBlock
    }
}
