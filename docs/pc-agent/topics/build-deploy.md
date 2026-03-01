# PC 빌드/배포

## 목적
로컬 실행, EXE/MSIX 빌드, 스토어 제출 전 점검 항목을 한 곳에서 확인한다.

## 로컬 실행

```powershell
cd C:\ProgressEye\pc-agent
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
venv\Scripts\python.exe main.py
```

OCR 모드 사용 시:

```powershell
venv\Scripts\python.exe setup_tesseract.py
```

## EXE 빌드 (Nuitka)

```powershell
cd C:\ProgressEye\pc-agent
powershell -ExecutionPolicy Bypass -File .\packaging\scripts\build_exe.ps1 -Clean
```

출력:
- `pc-agent/dist/ProgressEye/ProgressEye.exe`

## MSIX 빌드 (Microsoft Store)

1) Partner Center 식별값 설정

```powershell
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1
```

2) EXE + MSIX 빌드

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -SkipSign
```

출력:
- `pc-agent/dist/msix/ProgressEye_<version>_<arch>.msix`

## MSIX 에셋

`pc-agent/packaging/msix/Assets/`는 다음 이미지를 사용한다.
- `StoreLogo.png` (50x50)
- `Square44x44Logo.png` (44x44)
- `Square150x150Logo.png` (150x150)

플레이스홀더가 자동 생성될 수 있으므로, 제출 전 최종 브랜딩 파일로 교체한다.

## 배포 전 보안 점검

절대 포함 금지:
- 서비스 계정 개인키
- 코드서명 인증서 개인키(`.pfx`)
- 토큰 덤프(`token.json`, refresh token)

점검 명령:

```powershell
rg -n "BEGIN PRIVATE KEY|service_account|token\.json|refresh_token|\.pfx|client_secret\.json" dist\ProgressEye -S
```

## 관련 문서
- 기술설계: `docs/pc-agent/technical-spec.md` (빌드/배포)
- 백엔드 배포: `docs/backend/topics/deploy.md`
