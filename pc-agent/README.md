# ProgressEye PC Agent

PC 화면의 진행바를 캡처하여 **진행바 픽셀 분석(OpenCV)** 또는 **OCR 숫자 감지(pytesseract)** 두 가지 모드로 진행률(%)을 산출하는 Windows 데스크톱 에이전트.

Firebase Realtime Database를 통해 모바일 앱과 실시간 양방향 동기화한다.

## 아키텍처

```
┌─────────────┐     Firebase RTDB      ┌─────────────┐
│  PC Agent   │ ──── 진행률 push ────→ │  Mobile App │
│  (Python)   │ ←─── 명령 SSE ──────── │  (Kotlin)   │
└──────┬──────┘                        └──────┬──────┘
       │          Firebase Storage            │
       ├──── 스크린샷 업로드 ──────────────────┘
       │          Firebase Firestore
       └──── 버전 체크 / plan 조회
```

### 통신 흐름

| 방향 | 채널 | 용도 |
|---|---|---|
| PC → Mobile | Firebase RTDB (REST PATCH) | 진행률, 상태, 하트비트 |
| Mobile → PC | Firebase RTDB (SSE 스트리밍) | 명령 (스크린샷 요청, 모니터링 제어) |
| PC → Mobile | Firebase Storage | 스크린샷 이미지 (JPEG) |
| PC ← Firestore | Firestore REST API (공개 읽기) | 강제 버전 체크 (appConfig/pc), plan 조회 |

## 실행 방법

```bash
cd C:\ProgressEye\pc-agent
venv\Scripts\python.exe main.py
```

## 배포 패키징 (EXE/MSIX)

Microsoft Store 배포용 EXE/MSIX 빌드 스크립트는 `packaging/README.md`를 참고.

## 최초 설정 (venv가 없는 경우)

```bash
cd C:\ProgressEye\pc-agent
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
venv\Scripts\python.exe main.py
```

## Tesseract OCR 설정 (OCR 모드 사용 시)

OCR 숫자 감지 모드를 사용하려면 Tesseract OCR 바이너리가 필요하다.

### 방법 1: 번들 설치 스크립트 (권장)

```bash
venv\Scripts\python.exe setup_tesseract.py
```

`pc-agent/tesseract/` 폴더에 Tesseract 바이너리와 tessdata를 자동으로 설치한다.

### 방법 2: winget으로 시스템 설치

```bash
winget install UB-Mannheim.TesseractOCR
```

## 주요 의존성

- `mss` — 화면 캡처
- `opencv-python-headless` — 진행바 탐지 (OpenCV 4전략)
- `pytesseract` — OCR 숫자 감지
- `google-auth` / `google-auth-oauthlib` — Google OAuth 2.0 로그인
- `requests` — Firebase REST API 호출
- `sseclient-py` — Firebase RTDB SSE 스트리밍 (명령 수신)
- `keyring` — Windows 자격증명 관리자에 토큰 안전 저장
- `PyQt6` — UI 프레임워크 (다크 테마)
- `psutil` — CPU 사용량 모니터링
- `nvidia-ml-py` — NVIDIA GPU 사용량·온도 모니터링

## 주요 기능

### 모니터링

- **진행바 모드**: **영역 선택 시**: OpenCV 4전략(Canny+Otsu, 적응형이진화, HSV채도분할, 배경제거) + Sobel 트랙 확장으로 바 탐지. **모니터링 중**: bar_analyzer만 사용 (bar_finder 미사용)
- **OCR 모드**: pytesseract LSTM 숫자 감지, 변화 감지로 불필요한 OCR 스킵
- **멀티모니터 지원**: Qt screen index + mss monitor index + scale factor 자동 계산
- **작업별 완료 알람**: 80~100% 범위에서 threshold 설정, 연속 2회 도달 시 트레이 알림
- **이미지 변경 감지**: 최초 등록 시점의 템플릿 이미지와 비교 (64×64 grayscale + Pearson 상관계수), 화면이 크게 변경되면 자동 정지
- **프리징 감지**: 설정 시간(1~60분) 동안 진행률 변화 없으면 멈춤으로 판정
- **템플릿 이미지 영구 저장**: `templates/{region_id}.png`에 영역 등록 시점의 스크린샷을 저장, 작업 삭제 시에만 파일 삭제
- **모니터 절전 방지**: 모니터링 중 `SetThreadExecutionState`로 모니터 절전을 자동 방지, 정지 시 복귀
- **완료 지연 시간**: 작업별 0~60분 완료 확인 지연 설정, threshold 도달 후 설정 시간 유지 확인

### 모바일 연동

- **SSE 리스너**: Firebase RTDB `users/{uid}/commands/` 경로를 실시간 감시, 모바일 명령 즉시 수신
- **스크린샷 요청**: 모바일에서 명령 → PC 전체 화면 캡처 → JPEG 압축 → Firebase Storage 업로드 → RTDB에 URL 기록
- **forceLogout**: 모바일 회원 탈퇴 시 PC Agent 로그아웃 + 앱 종료
- **강제 버전 체크**: Firestore `appConfig/pc`에서 최소 버전 확인 (로그인 전, 인증 불필요)

### 완료 시나리오 (3가지)

| 시나리오 | 조건 | 처리 |
|---|---|---|
| 게이지 초기화 | 진행률이 threshold 근처에서 급락 (≥20% 하락) | 완료 알람 + 추적 초기화 |
| 창 닫힘/화면 변경 | 이미지 변경 감지 + 진행률 ≥ (threshold - 10%) | 완료 알람 |
| 게이지 유지 | 연속 2회 threshold 도달 | 완료 알람 (스파이크 방지) |

### Firebase 연동

- **인증**: Google OAuth → Firebase REST API (`signInWithIdp`)로 토큰 교환
- **토큰 자동 갱신**: 만료 5분 전 자동 refresh (1시간 유효)
- **배치 전송**: 모니터링 사이클 단위로 변경된 작업만 전송 (동일 데이터 스킵)
- **SSL 재시도**: `requests.Session` + `Retry(total=3, backoff_factor=1)`
- **Free/Pro 플랜**: plan은 Firestore `users/{uid}`에서 읽음. Free = 동시 1대, Pro = 무제한 기기

### Firebase 데이터 구조

```
users/{uid}/
  activeDevice: "pc_xxxx"
  profile: {email, displayName, lastLoginAt}
  mobileSession/
    sessionId, deviceId, deviceName, updatedAt
  mobileHeartbeat: <timestamp_ms>
  deviceStatus/
    {deviceId}: "monitoring" | "online" | "offline"
  heartbeat/
    {deviceId}: <timestamp_ms>
  commands/                    ← 모바일 → PC 명령 채널
    screenshot: {ts, cmdId}
    monitor: {action: "start" | "stop", ts, cmdId}
    forceLogout: {ts}
  devices/
    {pcId}/
      name, platform, appVersion, createdAt
      stats/
        cpu: <0-100>
        gpu: <0-100>
        ram: <0-100>
      screenshots/latest: {url, ts}
      tasks/
        {taskId}/
          p: <progress>
          s: "r"|"f"|"c"|"i"
          l: "작업이름"
  alerts/
    {alertId}/
      type: "completion"|"stall"|"image_change"
      title: "ProgressEye"
      body: "알림 메시지"
      deviceId: "pc_xxxx"
      ts: <timestamp_ms>
  fcmTokens/
    {tokenId}/
      token: "FCM 토큰 문자열"
      updatedAt: <server_timestamp>
```

### Firestore 데이터 구조

```
appConfig/pc       → { minVersion: "1.0.0" }     # 공개 읽기 (강제 업데이트)
users/{uid}        → { plan: "free" | "pro" }    # owner 읽기 (구독 상태)
```

### Firebase 비용 (Spark 무료 플랜)

| 서비스 | 무료 한도 | 예상 사용량 (1인) |
|---|---|---|
| RTDB 다운로드 | 10GB/월 | ~22MB/월 |
| RTDB 동시접속 | 100 | 2~3 (PC + 모바일) |
| Storage 저장 | 5GB | 수십MB (자동 정리) |
| Storage 다운로드 | 1GB/일 | 수MB/일 |

## 성능 최적화

### 바 모드 — 정확도 우선 분석

진행바 픽셀 분석은 현재 정확도 우선으로 동작하며, 다운스케일 경로는 제거되었다.
Windows/Linux 환경별 하드웨어 샘플러를 사용하며, 초기 워밍업 구간은 CPU 값을 전송하지 않고 `N/A`로 처리한다.

### OCR 모드 — 변화 감지 + LSTM-only

OCR 모드에서는 두 가지 최적화를 적용한다:

**1. 변화 감지 (Change Detection)**
- 이전 캡처와 픽셀을 비교하여 변화가 없으면 OCR을 스킵하고 캐시된 결과를 반환
- 이미지를 32×32로 축소 후 MD5 해싱으로 빠른 비교
- 효과: OCR 실행 72~107ms → skip 시 0.1~2ms (**50~500배 절약**)

**2. Tesseract 설정 최적화**
- `--oem 1` (LSTM only): Legacy+LSTM 대비 가벼움
- `--psm 6` (블록 모드): 다양한 레이아웃 호환성 유지
- 숫자+% 필터링은 regex로 처리 (화면 캡처에 비숫자 요소 포함 가능)

### 저사양 PC 예상 점유율 (2코어 Celeron, 4GB RAM)

| 시나리오 | CPU 평균 | 메모리 |
|---|---|---|
| 유휴 (대기) | ~0.5% | ~80~100MB |
| 바 모드 60초 주기 | ~2~4% | ~120~150MB |
| OCR 모드 60초 주기 (변화 없으면 skip) | ~0.5~1% | ~130~170MB |
| 바 모드 1초 주기 | ~10~15% | ~130MB |

## UI/설정

- **다크 테마**: 커스텀 색상 팔레트 (`#0f0f1a` ~ `#3b82f6`)
- **설정 오버레이**: MainWindow 내부 모달 (모니터링 간격, 언어, 프리징 감지 시간, 계정 정보, 로그아웃)
- **웰컴 가이드**: 최초 로그인 시 2단계 위저드 (언어 선택 → 절전 방지 안내 + 설정)
- **버튼 Tooltip**: 모든 버튼에 기능 설명 Tooltip 표시
- **다국어**: 한국어 / 영어 (i18n 모듈, 기본 언어: English)
- **로그아웃**: 토큰 삭제 → 앱 종료
- **시스템 트레이 제거**: 닫기 버튼 클릭 시 즉시 종료

## 프로젝트 구조

```
pc-agent/
├── main.py                  # 앱 진입점, 모니터링 루프, Firebase 전송
├── config.py                # 설정 관리 (JSON 파일 기반)
├── auth/
│   ├── google_oauth.py      # Google OAuth 2.0 로그인
│   ├── firebase_auth.py     # Firebase REST API 인증
│   └── token_manager.py     # keyring 토큰 저장/로드/갱신
├── core/
│   ├── capturer.py          # mss 화면 캡처 (멀티모니터)
│   ├── bar_finder.py        # OpenCV 4전략 진행바 탐지
│   ├── bar_analyzer.py      # 바 fill 비율 계산 (그라데이션 지원)
│   ├── ocr_reader.py        # pytesseract OCR 숫자 감지
│   ├── freeze_detector.py   # 프리징 감지
│   ├── scheduler.py         # 모니터링 스케줄러
│   └── system_monitor.py   # CPU/GPU/RAM 샘플러 (Windows/Linux 분기)
├── firebase/
│   ├── realtime_db.py       # Firebase RTDB REST API 래퍼
│   ├── command_listener.py  # SSE 명령 수신 (screenshot, monitor, forceLogout)
│   ├── storage.py           # Firebase Storage 스크린샷 업로드
│   └── device_manager.py    # 기기 등록/충돌 관리
├── ui/
│   ├── main_window.py       # PyQt6 메인 윈도우
│   ├── settings_dialog.py   # 설정 오버레이 (웰컴 위저드 포함)
│   ├── area_selector.py     # 영역 선택 투명 오버레이
│   ├── color_picker.py      # 바 색상 선택
│   ├── ocr_preview.py       # OCR 미리보기 다이얼로그
│   ├── region_viewer.py     # 선택 영역 하이라이트
│   └── tray_icon.py         # (레거시) 트레이 아이콘 모듈
├── utils/
│   ├── i18n.py              # 한/영 번역 모듈
│   └── logger.py            # 로깅 설정
├── templates/               # 영역 등록 시점 스크린샷 (런타임 생성)
├── tesseract/               # Tesseract 바이너리 (setup_tesseract.py로 설치)
├── setup_tesseract.py       # Tesseract 자동 설치 스크립트
└── requirements.txt         # Python 의존성
```

## Google OAuth 설정

client_secret.json 파일은 더 이상 사용하지 않는다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
2. 기본값(client_id/client_secret)은 앱에 내장되어 별도 설정 없이 동작 (Google Desktop App의 client_secret은 공개값 취급)
3. 앱 실행 시 OS 기본 브라우저가 열리며 Google 로그인 진행 → `localhost:8080`으로 리다이렉트되어 토큰 수신
4. 이후 실행부터는 keyring에 저장된 토큰으로 자동 로그인
