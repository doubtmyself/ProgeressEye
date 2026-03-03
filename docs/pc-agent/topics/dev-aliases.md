# PC 개발용 터미널 축약어 (PowerShell)

## 목적
PC Agent 개발 시 반복 입력을 줄이기 위해 PowerShell 축약어(`pe-*`)를 제공한다.

## 축약어 스크립트 위치
- `pc-agent/scripts/dev-aliases.ps1`

## 1회 로드(현재 터미널 세션)

```powershell
. C:\ProgressEye\pc-agent\scripts\dev-aliases.ps1
```

아래처럼 호출해도 동작한다(스크립트가 함수들을 global scope에 등록함):

```powershell
& C:\ProgressEye\pc-agent\scripts\dev-aliases.ps1
```

## 자동 로드(매번 터미널 시작 시)

PowerShell 프로필(`$PROFILE.CurrentUserAllHosts`)에 아래 1줄을 추가한다.

```powershell
. C:\ProgressEye\pc-agent\scripts\dev-aliases.ps1
```

## 제공 명령

- `pe-root`: 프로젝트 루트(`C:\ProgressEye`)로 이동
- `pe-pc`: PC Agent 디렉터리(`C:\ProgressEye\pc-agent`)로 이동
- `pe-docs`: 문서 디렉터리(`C:\ProgressEye\docs`)로 이동
- `pe-run`: PC Agent 실행(`main.py`)
- `pe-ocr-setup`: Tesseract 초기 설정(`setup_tesseract.py`)
- `pe-test [suite]`: 테스트 스크립트 실행
  - suite: `detection`, `downscale`, `ocr-accuracy`, `ocr-optimize`, `all`(기본값)
- `pe-exe`: EXE 증분 빌드(기본, 빠름)
- `pe-exe-clean`: EXE 클린 빌드(느리지만 가장 안전)
- `pe-exe-fast`: EXE 고속 빌드(PaddleOCR/PyMuPDF fallback 경로 제외)
- `pe-exe-run`: `pe-exe`로 생성된 EXE 실행(`dist/ProgressEye/ProgressEye.exe`)
- `pe-msix`: 빠른 Store MSIX 빌드(증분 EXE + FastExe + 병렬 컴파일)
- `pe-msix-clean`: 클린 Store MSIX 빌드(릴리스 직전 권장, FastExe 포함)
- `pe-git ...`: 프로젝트 루트 기준으로 `git` 명령 실행
- `peh`: PowerShell `Get-Help` 별칭

## 사용 예시

```powershell
pe-pc
pe-run
pe-ocr-setup
pe-test detection
pe-exe
pe-exe-fast
pe-exe-run
pe-msix
pe-msix-clean
pe-git status
```

기본 성능 설정:
- `pe-exe*` / `pe-msix*`는 `-NuitkaJobs 0`으로 실행되어, 실행 PC의 코어 수를 자동으로 사용한다.
