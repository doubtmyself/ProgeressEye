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

참고:
- 현재 PC 앱 배포 OCR 엔진은 ONNX Runtime 기반 RapidOCR 기준이다.

## EXE 빌드 (Nuitka)

```powershell
cd C:\ProgressEye\pc-agent
powershell -ExecutionPolicy Bypass -File .\packaging\scripts\build_exe.ps1 -Clean
```

선택 옵션:
- `-Fast`: `paddleocr/pdf2docx/pymupdf` 경로를 제외해 빌드 시간 단축(대신 해당 fallback 미포함)
- `-EnableUpx`: UPX가 설치된 경우 exe/dll/pyd 압축 시도
- `-SkipBundleVCRuntime`: VC++ 런타임 DLL 자동 번들링 단계를 건너뜀
- `-UpxExe "C:\path\to\upx.exe"`: UPX 경로 직접 지정

개발 중 빠른 반복 빌드 권장:
- `-Clean` 없이 실행해 증분 빌드 사용
- fallback 경로가 필요 없으면 `-Fast` 사용

클린 빌드 잠금 처리:
- `-Clean` 실행 시 빌드 스크립트가 `dist` 경로를 잠그는 `ProgressEye.exe`(및 관련 프로세스)를 자동 종료 후 삭제를 재시도한다.
- `Remove-Item ... 다른 프로세스에서 사용 중` 오류가 났던 케이스를 줄이기 위한 동작이다.

출력:
- `pc-agent/dist/ProgressEye/ProgressEye.exe`

빌드 스크립트는 기본적으로 불필요한 대용량 파일(예: OpenCV video DLL, NumPy 테스트 모듈, Qt PDF DLL 등)을 제거해 배포 폴더 용량을 줄인다.
또한 기본적으로 Visual C++ Redistributable DLL(`msvcp140.dll`, `vcomp140.dll` 등)을 배포 폴더에 자동 포함해, 타깃 PC에 재배포 패키지가 없는 경우에도 실행 호환성을 높인다.

## MSIX 빌드 (Microsoft Store)

1) Partner Center 식별값 설정

```powershell
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1
```

2) EXE + MSIX 빌드

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -SkipSign
```

버전 규칙(스토어 제출):
- `partner-center.identity.ps1`의 `$Version`은 `x.y.z.0` 형식만 사용한다.
- 릴리스마다 `z`를 1씩 증가시키고, 4번째 자리(Revision)는 항상 `0`으로 유지한다.

속도 최적화 옵션:
- `-FastExe`: EXE 단계에서 PaddleOCR/PyMuPDF fallback 경로를 제외해 컴파일 시간을 줄인다.
- `-NuitkaJobs <N>`: Nuitka 병렬 컴파일 스레드 수를 지정한다(기본값 0 = CPU 코어 수 자동 사용).
- 개발 중에는 `-CleanExe`를 생략해 증분 빌드를 사용하고, 릴리스 직전에만 `-CleanExe`를 권장한다.

MSIX 패키징 안정성 참고:
- `make_msix.ps1`는 `MakeAppx 0x8007007b`를 유발할 수 있는 `python-docx` 템플릿 메타데이터 파일들을 스테이징에서 자동 제거한다.

출력:
- `pc-agent/dist/msix/ProgressEye_<version>_<arch>.msix`

스토어 배포 권장 런타임 전략:
- MSIX 매니페스트에서 `Microsoft.VCLibs.140.00.UWPDesktop` 의존성을 선언해, 설치 시 VC++ 런타임을 자동으로 맞춘다.
- 따라서 스토어 경로에서는 `-SkipBundleVCRuntime`를 사용하지 않는 것을 권장한다.

OCR 런타임 호환성 가이드:
- 앱 시작 시 RapidOCR(ONNX Runtime) 초기화 실패가 감지되면 PaddleOCR 호환 모드로 자동 전환한다.
- 이 경우 앱에서 안내 다이얼로그를 1회 표시하며, 모니터링은 그대로 동작한다(추가 설치 필수 아님).
- 성능 개선이 필요할 때만 VC++ 재배포 패키지/드라이버/Windows 업데이트를 권장한다.

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
- 개발용 축약어: `docs/pc-agent/topics/dev-aliases.md`
