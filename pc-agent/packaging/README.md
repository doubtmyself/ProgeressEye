# PC Agent 패키징 (EXE + Microsoft Store MSIX)

이 디렉터리는 Microsoft Store 릴리스를 위한 재현 가능한 패키징 절차를 제공합니다.

## 1) EXE 빌드 (Nuitka)

Nuitka는 Python 코드를 C로 변환 후 네이티브 바이너리로 컴파일합니다. 디컴파일이 불가능하여 코드 보호에 효과적입니다.

**요구사항:**

- Python 3.11+
- C 컴파일러: Nuitka가 MinGW64를 자동 다운로드하거나, MSVC(Visual Studio Build Tools) 사용 가능
- 첫 빌드 시 수 분 소요 (이후 C 레벨 캐시로 빌드 속도 향상)

`pc-agent/` 경로에서 실행:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\scripts\build_exe.ps1 -Clean
```

출력:

- `dist\ProgressEye\ProgressEye.exe`

참고:

- Nuitka `--standalone` 모드로 self-contained 폴더를 생성합니다.
- OAuth는 PKCE를 사용하며, client ID를 `PROGRESSEYE_GOOGLE_CLIENT_ID`에서 읽습니다.
- `PROGRESSEYE_GOOGLE_CLIENT_SECRET`은 선택값이며 기본은 빈 값(미사용)입니다.
- PyQt6 플러그인이 자동 번들링됩니다 (`--enable-plugin=pyqt6`).
- Tesseract OCR 번들(174MB)과 templates 폴더가 dist에 포함됩니다.

## 2) MSIX 패키지 빌드

요구사항:

- Windows SDK 도구가 PATH에 있어야 함 (`makeappx.exe`, 선택적으로 `signtool.exe`)
- Partner Center에서 발급된 앱 식별 값

예시:

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

출력:

- `dist\msix\ProgressEye_<version>_<arch>.msix`

### Partner Center 고정 명령 플로우 (권장)

1. identity 템플릿을 복사하고 실제 Partner Center 값으로 채웁니다:

```powershell
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1
```

`partner-center.identity.ps1` 편집:

- `$IdentityName`: Partner Center `Package/Identity/Name`
- `$Publisher`: Partner Center Publisher subject (예: `CN=...`)
- `$PublisherDisplayName`, `$DisplayName`, `$Version`, `$Architecture`

2. 한 번의 명령으로 EXE + MSIX 빌드:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -SkipSign
```

3. 선택: 사이드로드 테스트용 로컬 서명:

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -PfxPath "C:\certs\progresseye-dev.pfx" -PfxPassword "your-password"
```

### 선택: 로컬 서명 (사이드로드 설치용)

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\make_msix.ps1 \
  -IdentityName "YourPublisher.ProgressEye" \
  -Publisher "CN=YOUR_PUBLISHER_SUBJECT" \
  -Version "1.0.0.0" \
  -PfxPath "C:\certs\progresseye-dev.pfx" \
  -PfxPassword "your-password"
```

## 3) Microsoft Store 체크리스트

- `Identity Name`과 `Publisher`를 Partner Center 값과 정확히 일치시키세요.
- 버전 형식은 `A.B.C.0`을 유지하세요.
- `packaging\msix\Assets\` 아래 플레이스홀더 로고를 실제 브랜딩 PNG로 교체하세요.
- 제출 전, 패키징된 EXE와 MSIX를 로컬에서 실행해 확인하세요.

## 포함된 보안 기본값

- 패키징된 빌드(`__compiled__` 또는 `sys.frozen`)는 `-d/--debug` UI 테스트 버튼 활성화를 무시합니다.
- 일반 설치 사용자에게 테스트 버튼은 계속 숨김 처리됩니다.
- Nuitka 네이티브 컴파일로 소스 코드가 보호됩니다 (디컴파일 불가).

## 빌드 도구 참고

- Nuitka 빌드 스크립트: `packaging/scripts/build_exe_nuitka.ps1`
- PyInstaller spec (레거시 참조용): `packaging/pyinstaller/progresseye.spec`

## 배포 전 민감정보 체크리스트

### 포함 가능(공개 전제)
- `OAuth client_id`
- Desktop OAuth에서 요구되는 `client_secret` (PKCE 사용 전제, 노출 가능 값으로 운영)
- Firebase Web API Key (`AIza...`)  
  (서버 비밀키가 아니며, Firebase Rules/Auth 검증이 실제 보안 경계)

### 절대 포함 금지
- Service Account JSON/Private Key (`-----BEGIN PRIVATE KEY-----`)
- 코드 서명 인증서 개인키 파일 (`.pfx`)
- 로컬 토큰 파일 (`token.json`, `refresh token` 덤프)
- 개인 PC 설정/캐시 파일 (`.firebase/`, 개발자 로컬 경로 정보)

### 현재 배포 스크립트 기준 확인 포인트
1. MSIX는 `dist\ProgressEye`만 패키징됨 (`make_msix.ps1`)
2. EXE 빌드에서 `resources`, `templates`, `tesseract`가 포함됨 (`build_exe_nuitka.ps1`)
3. 따라서 민감파일은 `dist\ProgressEye`와 위 포함 디렉터리에 없어야 함

### 배포 직전 권장 점검
```powershell
rg -n "BEGIN PRIVATE KEY|service_account|token\.json|refresh_token|\.pfx|client_secret\.json" dist\ProgressEye -S
```

문제 키워드가 발견되면 배포를 중단하고 파일을 제외한 뒤 다시 빌드하세요.
