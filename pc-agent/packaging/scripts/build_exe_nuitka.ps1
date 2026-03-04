Param(
    [string]$PythonExe = "",
    [switch]$Clean,
    [switch]$Fast,
    [switch]$EnableUpx,
    [switch]$SkipBundleVCRuntime,
    [int]$NuitkaJobs = 0,
    [string]$UpxExe = ""
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

function Stop-LockingProcesses {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathPrefix
    )

    if (-not (Test-Path $PathPrefix)) {
        return
    }

    $normalizedPrefix = [System.IO.Path]::GetFullPath($PathPrefix).TrimEnd("\")
    $killed = $false

    # First, stop well-known names.
    foreach ($proc in @("ProgressEye", "main")) {
        $procs = Get-Process -Name $proc -ErrorAction SilentlyContinue
        foreach ($p in $procs) {
            try {
                Stop-Process -Id $p.Id -Force -ErrorAction Stop
                Write-Host "[build_exe_nuitka] Stopped process by name: $($p.ProcessName) (PID=$($p.Id))"
                $killed = $true
            } catch {
            }
        }
    }

    # Then, stop any process whose executable is under the target path.
    $candidates = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        if (-not $_.ExecutablePath) { return $false }
        try {
            $exePath = [System.IO.Path]::GetFullPath($_.ExecutablePath)
            return $exePath.StartsWith($normalizedPrefix, [System.StringComparison]::OrdinalIgnoreCase)
        } catch {
            return $false
        }
    }

    foreach ($proc in $candidates) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
            Write-Host "[build_exe_nuitka] Stopped locking process: $($proc.Name) (PID=$($proc.ProcessId))"
            $killed = $true
        } catch {
        }
    }

    # Fallback: kill by image name/process tree (helps when parent/child keeps handle).
    # Ignore "not found" case and silence taskkill output.
    foreach ($image in @("ProgressEye.exe", "main.exe")) {
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "taskkill /F /T /IM $image >nul 2>&1" -NoNewWindow -Wait -ErrorAction SilentlyContinue | Out-Null
    }

    if ($killed) {
        Start-Sleep -Milliseconds 600
    }
}

function Remove-PathWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,
        [int]$MaxRetries = 5
    )

    if (-not (Test-Path $TargetPath)) {
        return
    }

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        Stop-LockingProcesses -PathPrefix $TargetPath

        try {
            # Clear read-only attributes recursively first
            Get-ChildItem -Path $TargetPath -Recurse -Force -ErrorAction SilentlyContinue |
                ForEach-Object {
                    try { $_.IsReadOnly = $false } catch {}
                }

            Remove-Item $TargetPath -Recurse -Force -ErrorAction Stop
            return
        }
        catch {
            if ($attempt -ge $MaxRetries) {
                throw
            }
            Start-Sleep -Milliseconds (300 * $attempt)
        }
    }
}

function Remove-UnusedPayloadFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DistRoot
    )

    $removedMB = 0
    $removeFilePatterns = @(
        "cv2\opencv_videoio_ffmpeg*.dll",    # video I/O runtime, unused by image-only capture
        "numpy.libs\libscipy_openblas*.dll",  # heavy BLAS payload, not required for current usage
        "numpy\_core\_multiarray_tests.pyd",  # numpy test extension
        "qt6pdf.dll",                          # Qt PDF module not used by app
        "qtwebengine_devtools_resources.debug.pak",
        "qtwebengine_resources.debug.pak",
        "qtwebengine_resources_100p.debug.pak",
        "qtwebengine_resources_200p.debug.pak"
    )

    foreach ($pattern in $removeFilePatterns) {
        $glob = Join-Path $DistRoot $pattern
        Get-Item $glob -ErrorAction SilentlyContinue | ForEach-Object {
            $sizeMB = [math]::Round($_.Length / 1MB, 1)
            Write-Host "[build_exe_nuitka] Removing $($_.Name) ($sizeMB MB)"
            $removedMB += $sizeMB
            Remove-Item $_.FullName -Force
        }
    }

    $removeDirs = @(
        (Join-Path $DistRoot "numpy\tests"),
        (Join-Path $DistRoot "PIL\Tests"),
        (Join-Path $DistRoot "__pycache__")
    )

    foreach ($dir in $removeDirs) {
        Get-Item $dir -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "[build_exe_nuitka] Removing directory $($_.FullName)"
            Remove-Item $_.FullName -Recurse -Force
        }
    }

    Get-ChildItem -Path $DistRoot -Recurse -Filter "*.pyi" -File -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item $_.FullName -Force
        }

    Write-Host "[build_exe_nuitka] Removed unused payload (~$removedMB MB + metadata files)"
}

function Resolve-UpxExecutable {
    param([string]$ExplicitPath)

    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return (Resolve-Path $ExplicitPath).Path
    }

    $upxCmd = Get-Command "upx" -ErrorAction SilentlyContinue
    if ($upxCmd) {
        return $upxCmd.Source
    }

    return $null
}

function Compress-WithUpx {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DistRoot,
        [string]$UpxPath
    )

    if (-not $UpxPath) {
        Write-Host "[build_exe_nuitka] UPX not found. Skipping binary compression."
        return
    }

    Write-Host "[build_exe_nuitka] UPX compression started: $UpxPath"
    $targets = Get-ChildItem -Path $DistRoot -Recurse -Include "*.exe", "*.pyd", "*.dll" -File -ErrorAction SilentlyContinue
    foreach ($file in $targets) {
        & $UpxPath --best --lzma --quiet $file.FullName
    }
    Write-Host "[build_exe_nuitka] UPX compression completed"
}

function Copy-VcRuntimeDlls {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DistRoot
    )

    $requiredDlls = @(
        "msvcp140.dll",
        "vcomp140.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "concrt140.dll"
    )

    $searchRoots = @(
        $env:SystemRoot,
        ${env:ProgramFiles(x86)},
        $env:ProgramFiles,
        ${env:ProgramFiles(x86)} + "\Microsoft Visual Studio",
        $env:ProgramFiles + "\Microsoft Visual Studio"
    ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    $bundledCount = 0
    $missing = @()
    foreach ($dll in $requiredDlls) {
        $dest = Join-Path $DistRoot $dll
        if (Test-Path $dest) {
            continue
        }

        $candidates = @()
        foreach ($root in $searchRoots) {
            $direct1 = Join-Path $root "System32\$dll"
            $direct2 = Join-Path $root "SysWOW64\$dll"
            if (Test-Path $direct1) { $candidates += $direct1 }
            if (Test-Path $direct2) { $candidates += $direct2 }

            try {
                $found = Get-ChildItem -Path $root -Filter $dll -File -Recurse -ErrorAction SilentlyContinue |
                    Select-Object -ExpandProperty FullName
                if ($found) { $candidates += $found }
            } catch {
            }
        }

        $source = $candidates | Select-Object -First 1
        if ($source) {
            Copy-Item $source $dest -Force
            Write-Host "[build_exe_nuitka] Bundled VC runtime: $dll"
            $bundledCount += 1
        } else {
            $missing += $dll
        }
    }

    if ($missing.Count -gt 0) {
        Write-Warning "[build_exe_nuitka] Missing VC runtime DLLs: $($missing -join ', ')"
        Write-Warning "[build_exe_nuitka] Install Microsoft Visual C++ Redistributable 2015-2022 (x64) on target machines if these are not bundled."
    } else {
        Write-Host "[build_exe_nuitka] VC runtime bundling complete ($bundledCount copied)"
    }
}

Push-Location $PcAgentRoot
try {
    if ($NuitkaJobs -le 0) {
        $NuitkaJobs = [Environment]::ProcessorCount
    }
    $NuitkaJobs = [Math]::Max(1, $NuitkaJobs)
    Write-Host "[build_exe_nuitka] Nuitka jobs: $NuitkaJobs"

    if ($Clean) {
        # Stop possibly running app/processes that can lock dist artifacts (.exe/.pyd)
        Stop-LockingProcesses -PathPrefix (Join-Path $PcAgentRoot "dist")

        foreach ($dir in @("build", "dist", "main.build", "main.dist", "main.onefile-build")) {
            $p = Join-Path $PcAgentRoot $dir
            if (Test-Path $p) {
                Write-Host "[build_exe_nuitka] Removing $dir"
                Remove-PathWithRetry -TargetPath $p
            }
        }
    }

    # Install/upgrade Nuitka + ordered-set (improves build performance)
    & $PythonExe -m pip install --upgrade nuitka ordered-set

    # Run Nuitka standalone build
    $nuitkaArgs = @(
        "-m", "nuitka",
        "--standalone",
        "--jobs=$NuitkaJobs",
        "--output-filename=ProgressEye.exe",
        "--output-dir=dist",
        "--windows-console-mode=disable",
        "--windows-icon-from-ico=resources/app-icon.ico",
        "--enable-plugin=pyqt6",
        "--python-flag=no_docstrings",
        "--include-package=google.auth",
        "--include-package=google.oauth2",
        "--include-package=google_auth_oauthlib",
        "--include-package=rapidocr_onnxruntime",
        "--include-package=onnxruntime",
        "--include-package-data=google.auth",
        "--include-package-data=google_auth_oauthlib",
        "--include-data-dir=templates=templates",
        "--include-data-dir=resources=resources",
        "--nofollow-import-to=tkinter",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=pytest",
        "--nofollow-import-to=unittest",
        "--nofollow-import-to=test",
        "--nofollow-import-to=tests",
        "main.py"
    )

    if ($Fast) {
        # PaddleOCR fallback chain pulls in heavy PDF modules and slows compile drastically.
        $nuitkaArgs += @(
            "--nofollow-import-to=paddleocr",
            "--nofollow-import-to=pdf2docx",
            "--nofollow-import-to=pymupdf",
            "--nofollow-import-to=fitz"
        )
        Write-Host "[build_exe_nuitka] Fast mode enabled: excluding PaddleOCR/PyMuPDF fallback path"
    }

    & $PythonExe @nuitkaArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Nuitka compilation failed with exit code $LASTEXITCODE"
    }

    # Nuitka outputs to dist/main.dist/ — rename to dist/ProgressEye/ for MSIX compatibility
    $nuitkaOut = Join-Path $PcAgentRoot "dist\main.dist"
    $targetDir = Join-Path $PcAgentRoot "dist\ProgressEye"

    if (Test-Path $targetDir) {
        Remove-PathWithRetry -TargetPath $targetDir
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

    Remove-UnusedPayloadFiles -DistRoot $targetDir

    if (-not $SkipBundleVCRuntime) {
        Copy-VcRuntimeDlls -DistRoot $targetDir
    } else {
        Write-Host "[build_exe_nuitka] Skipping VC runtime bundling by request"
    }

    if ($EnableUpx) {
        $resolvedUpx = Resolve-UpxExecutable -ExplicitPath $UpxExe
        Compress-WithUpx -DistRoot $targetDir -UpxPath $resolvedUpx
    }

    Write-Host "[build_exe_nuitka] Done: $exePath"
}
finally {
    Pop-Location
}
