# PC Agent Packaging (EXE + Microsoft Store MSIX)

This directory provides a repeatable packaging flow for Microsoft Store release.

## 1) Build EXE (PyInstaller)

From `pc-agent/`:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\scripts\build_exe.ps1 -Clean
```

Output:

- `dist\ProgressEye\ProgressEye.exe`

Notes:

- The spec excludes test-related modules.
- OAuth uses PKCE and reads client ID from `PROGRESSEYE_GOOGLE_CLIENT_ID`.

## 2) Build MSIX package

Requirements:

- Windows SDK tools on PATH (`makeappx.exe`, optionally `signtool.exe`)
- App identity values from Partner Center

Example:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\make_msix.ps1 \
  -IdentityName "YourPublisher.ProgressEye" \
  -Publisher "CN=YOUR_PUBLISHER_SUBJECT" \
  -PublisherDisplayName "Your Company" \
  -DisplayName "ProgressEye" \
  -Version "1.0.0.0" \
  -Architecture "x64" \
  -SkipSign
```

Output:

- `dist\msix\ProgressEye_<version>_<arch>.msix`

### Partner Center fixed-command flow (recommended)

1. Copy identity template and fill real Partner Center values:

```powershell
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1
```

Edit `partner-center.identity.ps1`:

- `$IdentityName`: Partner Center `Package/Identity/Name`
- `$Publisher`: Partner Center Publisher subject (for example `CN=...`)
- `$PublisherDisplayName`, `$DisplayName`, `$Version`, `$Architecture`

2. Build EXE + MSIX in one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -SkipSign
```

3. Optional local signing for sideload test:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -PfxPath "C:\certs\progresseye-dev.pfx" -PfxPassword "your-password"
```

### Optional local signing (for sideload install)

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\make_msix.ps1 \
  -IdentityName "YourPublisher.ProgressEye" \
  -Publisher "CN=YOUR_PUBLISHER_SUBJECT" \
  -Version "1.0.0.0" \
  -PfxPath "C:\certs\progresseye-dev.pfx" \
  -PfxPassword "your-password"
```

## 3) Microsoft Store checklist

- Set `Identity Name` and `Publisher` to exactly match Partner Center values.
- Keep version format `A.B.C.0`.
- Replace placeholder logos under `packaging\msix\Assets\` with real branded PNGs.
- Run app locally from the packaged EXE and MSIX before submission.

## Security defaults included

- Packaged (`sys.frozen`) builds ignore `-d/--debug` UI test-button activation.
- Test buttons remain hidden for normal installed users.
