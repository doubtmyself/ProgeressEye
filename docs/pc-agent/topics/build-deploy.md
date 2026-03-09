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
powershell -ExecutionPolicy Bypass -File .\packaging\scripts\build_exe.ps1 -Clean -Fast
```

선택 옵션:
- `-Fast`: FAST 빌드 기준(기본 정책과 동일, 호환용 옵션)
- `-OutputSubdir "ProgressEyeSlim"`: dist 하위 출력 폴더명을 지정(잠금 파일 회피/비교 빌드용)
- `-EnableUpx`: UPX가 설치된 경우 exe/dll/pyd 압축 시도
- `-SkipBundleVCRuntime`: VC++ 런타임 DLL 자동 번들링 단계를 건너뜀
- `-UpxExe "C:\path\to\upx.exe"`: UPX 경로 직접 지정

개발 중 빠른 반복 빌드 권장:
- `-Clean` 없이 실행해 증분 빌드 사용
- 기본 빌드가 이미 FAST OCR 기준이므로 `-Fast`는 선택 사항

클린 빌드 잠금 처리:
- `-Clean` 실행 시 빌드 스크립트가 `dist` 경로를 잠그는 `ProgressEye.exe`(및 관련 프로세스)를 자동 종료 후 삭제를 재시도한다.
- `Remove-Item ... 다른 프로세스에서 사용 중` 오류가 났던 케이스를 줄이기 위한 동작이다.

출력:
- `pc-agent/dist/ProgressEye/ProgressEye.exe`

빌드 스크립트는 기본적으로 불필요한 대용량 파일(예: OpenCV video DLL, NumPy 테스트 모듈, Qt PDF DLL 등)을 제거해 배포 폴더 용량을 줄인다.
또한 기본적으로 Visual C++ Redistributable DLL(`msvcp140.dll`, `vcomp140.dll` 등)을 배포 폴더에 자동 포함해, 타깃 PC에 재배포 패키지가 없는 경우에도 실행 호환성을 높인다.
또한 FAST 기준에서 `sympy`/`mpmath`를 자동 제외해 ONNX 체인으로 인한 EXE 비대화를 억제한다.
또한 OpenCV는 `opencv-python-headless` 단일 변형만 허용하며, `opencv-python`/`opencv-contrib-python`이 함께 설치된 빌드 환경에서는 실패 처리한다.

## MSIX 빌드 (Microsoft Store)

1) Partner Center 식별값 설정

```powershell
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1
```

2) EXE + MSIX 빌드

```powershell
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -FastExe -SkipSign
```

버전 규칙(스토어 제출):
- `partner-center.identity.ps1`의 `$Version`은 `x.y.z.0` 형식만 사용한다.
- 릴리스마다 `z`를 1씩 증가시키고, 4번째 자리(Revision)는 항상 `0`으로 유지한다.

속도 최적화 옵션:
- `-FastExe`: FAST 빌드 기준(기본 정책과 동일, 호환용 옵션)
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
- PC 빌드는 CPU 전용 `onnxruntime` + RapidOCR를 기준으로 한다.
- 빌드 스크립트는 `onnxruntime-gpu`가 감지되면 실패 처리하여 CUDA/cuDNN 대용량 DLL 유입을 차단한다.
- 빌드 스크립트는 OpenCV 혼합 설치(`opencv-python`, `opencv-contrib-python`)가 감지되면 실패 처리하며, `opencv-python-headless`만 허용한다.
- Paddle fallback 경로는 배포 빌드에서 사용하지 않는다(FAST 기준 고정).

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
