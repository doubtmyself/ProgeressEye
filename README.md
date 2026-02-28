# ProgressEye

PC 화면의 진행률을 실시간으로 추적하고, 모바일에서 모니터링하는 크로스플랫폼 시스템.

## 최근 업데이트 (2026-02)

- **회원 탈퇴**: 모바일 앱에서 계정 삭제 기능 추가 (연결된 모든 기기 로그아웃 + Firebase 데이터 삭제)
- **모니터링 파이프라인 리팩토링**: 영역 선택 시에만 bar_finder 사용, 모니터링 중에는 bar_analyzer만 사용 (불필요한 재탐지 제거)
- **완료 지연 시간**: 작업별 완료 게이지 도달 후 N분간 유지 확인 기능 추가
- **강제 버전 체크**: Firestore `appConfig/pc` 문서로 최소 버전 관리, 로그인 전 체크
- **Firestore 마이그레이션**: 사용자 plan 정보를 RTDB에서 Firestore로 이동 (`users/{uid}`)
- **forceLogout 명령**: 모바일에서 회원 탈퇴 시 PC Agent에 로그아웃 명령 전달
- **FCM 알림 정상화**: Cloud Functions에 notification 필드 추가, 런타임 알림 권한 요청 (Android 13+)
- **자동 배포**: Gradle Play Publisher(GPP) 4.0.0으로 Android 앱 자동 배포 파이프라인 구축
- **R8 난독화**: Release 빌드에 코드 난독화 + 리소스 축소 적용

```
┌─────────────┐     Firebase RTDB      ┌─────────────┐
│  PC Agent   │ ──── 진행률/알림 ────→ │  Mobile App │
│  (Python)   │ ←─── 명령 SSE ──────── │  (Kotlin)   │
└──────┬──────┘                        └──────┬──────┘
       │       Firebase Cloud Functions       │
       ├── alerts RTDB write ──→ FCM push ──→ 시스템 알림
       │       Firebase Firestore             │
       └── appConfig (버전체크) ───────────────┘
           users/{uid} (plan)
```

## 프로젝트 구조

```
ProgressEye/
├── pc-agent/          # Windows 데스크톱 에이전트 (Python, PyQt6)
├── mobile-app/        # Android 모바일 앱 (Kotlin, Jetpack Compose)
├── functions/         # Firebase Cloud Functions (Node.js)
├── privacy-polycy/    # 개인정보처리방침 호스팅 (Firebase Hosting)
├── database.rules.json
├── firestore.rules
└── firebase.json
```

## 사전 요구사항

| 도구 | 버전 | 용도 |
|---|---|---|
| Python | 3.11+ | PC Agent |
| Android Studio | 최신 | Mobile App 빌드 |
| Node.js | 20+ | Cloud Functions |
| Firebase CLI | 15+ | Firebase 배포 |
| Google Cloud 프로젝트 | `progresseye-49244` | Firebase 백엔드 |

### Firebase CLI 설치

```bash
npm install -g firebase-tools
firebase login
```

---

## PC Agent 빌드 & 실행

```bash
cd pc-agent

# 최초 설정
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt

# 실행
venv\Scripts\python.exe main.py
```

OCR 모드 사용 시 Tesseract 설치 필요:

```bash
venv\Scripts\python.exe setup_tesseract.py
```

자세한 내용은 [pc-agent/README.md](pc-agent/README.md) 참고.

### Microsoft Store용 MSIX 패키징

```powershell
cd pc-agent

# 1) Partner Center 값 파일 생성 후 값 입력
copy .\packaging\msix\partner-center.identity.ps1.example .\packaging\msix\partner-center.identity.ps1

# 2) EXE + MSIX 빌드 (스토어 업로드용 기본)
powershell -ExecutionPolicy Bypass -File .\packaging\msix\build_store_msix.ps1 -BuildExe -CleanExe -SkipSign
```

Partner Center 값(`IdentityName`, `Publisher`)은 반드시 실제 값과 정확히 일치해야 한다.
상세 절차는 [pc-agent/packaging/README.md](pc-agent/packaging/README.md) 참고.

---

## Mobile App 빌드

### Debug 빌드

```bash
cd mobile-app
gradlew.bat assembleDebug
```

APK 출력 경로: `mobile-app/app/build/outputs/apk/debug/app-debug.apk`

### Release 빌드

```bash
cd mobile-app
gradlew.bat assembleRelease
```

> Release 빌드에는 서명 설정이 필요합니다. `app/build.gradle.kts`의 `signingConfigs` 참고.

### Android Studio에서 빌드

1. Android Studio에서 `mobile-app/` 디렉토리 열기
2. Gradle sync 완료 대기
3. Run (Shift+F10) 또는 Build > Make Project

### Google Play Store 자동 배포

```bash
cd mobile-app
.\gradlew.bat publishBundle
```

Gradle Play Publisher(GPP) 4.0.0을 사용한 자동 배포. 사전 요구:
- `keystore.properties` — 서명 설정
- `app/google-play-api-key.json` — Google Play API 서비스 계정 키
- Google Play Console에서 앱 등록 + 첫 AAB 수동 업로드 완료
---

## Cloud Functions 배포

Cloud Functions는 RTDB `alerts` 노드에 새 문서가 생성되면 FCM data+notification 메시지를 모바일에 전송합니다.

### 의존성 설치

```bash
cd functions
npm install
```

### 배포

```bash
# 프로젝트 루트에서 실행
firebase deploy --only functions --project progresseye-49244
```

또는 npx 사용:

```bash
npx firebase-tools deploy --only functions --project progresseye-49244
```

### 배포 확인

```bash
# 함수 로그 확인
firebase functions:log --project progresseye-49244

# Firebase Console에서 확인
# https://console.firebase.google.com/project/progresseye-49244/functions
```

### 로컬 에뮬레이터 테스트

```bash
cd functions
npm run serve
```

---

## Firebase RTDB 규칙 배포

`database.rules.json` 수정 후:

```bash
firebase deploy --only database --project progresseye-49244
```

---

## Firestore 규칙 배포

`firestore.rules` 수정 후:

```bash
firebase deploy --only firestore:rules --project progresseye-49244
```

---

## 전체 배포 (한 번에)

```bash
# 프로젝트 루트에서
firebase deploy --project progresseye-49244
```

이 명령으로 Cloud Functions + RTDB 규칙 + Firestore 규칙 + Hosting이 모두 배포됩니다.

---

## Firebase 데이터 구조

```
users/{uid}/
  activeDevice: "pc_xxxx"
  profile: { email, displayName, lastLoginAt }
  mobileSession/
    sessionId: "uuid"
    deviceId: "android_xxx"
    deviceName: "Samsung SM-S9xx"
    updatedAt: <server_timestamp>
  mobileHeartbeat: <timestamp_ms>
  deviceStatus/
    {deviceId}: "monitoring" | "online" | "offline"
  heartbeat/
    {deviceId}: <timestamp_ms>
  commands/
    screenshot: { ts, cmdId }
    monitor: { action: "start" | "stop", ts, cmdId }
    forceLogout: { ts }
  devices/
    {pcId}/
      name, platform, appVersion, createdAt
      stats/                         # 하드웨어 모니터링
        cpu: <0-100>
        gpu: <0-100>
        ram: <0-100>
      screenshots/latest: { url, ts }
      tasks/
        {taskId}/
          p: <progress>          # 진행률 (0~100)
          s: "r"|"f"|"c"|"i"     # running/frozen/completed/idle
          l: "작업이름"           # label
  alerts/
    {alertId}/
      type: "completion" | "stall" | "image_change"
      title: "ProgressEye"
      body: "알림 메시지"
      deviceId: "pc_xxxx"
      ts: <timestamp_ms>
  fcmTokens/
    {tokenId}/
      token: "FCM 토큰 문자열"
      updatedAt: <server_timestamp>
```

### Firestore

```
appConfig/pc           → { minVersion: "1.0.0" }       # 공개 읽기 (PC 앱 강제 업데이트 체크)
users/{uid}            → { plan: "free" | "pro" }      # owner 읽기 (구독 상태)
```

## 알림 흐름

```
PC 이벤트 감지 (완료/프리징/화면변경)
  → PC 로컬 로그 기록
  → RTDB /alerts/{id} 기록
  → Cloud Function onAlertCreated 트리거
  → /fcmTokens 조회 → FCM data+notification message 전송
  → Mobile FCMService.onMessageReceived()
  → 사용자 설정 확인 (완료 알림 ON/OFF, 멈춤 경고 ON/OFF)
  → Android 시스템 알림 표시
  → AlertsViewModel RTDB 리스너로 앱 내 알림 목록 갱신
```

## 하드웨어 모니터링

PC Agent가 실행 중일 때 CPU/GPU 사용량을 모바일 대시보드에 실시간 표시합니다.

```
PC Agent (모니터링 중 / 하트비트 시)
  → Windows: GetSystemTimes 기반 CPU busy 계산(우선), psutil/PDH fallback
  → Linux: psutil CPU 사용량 (%)
  → nvidia-ml-py: NVIDIA GPU 사용량 (%) — 우선
  → Windows PDH: AMD/Intel GPU 사용량 (%) — fallback
  → RAM: psutil 최신값
  → RTDB /devices/{id}/stats/ 에 기록
  → Mobile ChildEventListener가 자동 감지
  → DeviceHeader에 칩 UI로 표시 (PC 온라인일 때만)
```

| 항목 | 라이브러리 | 관리자 권한 | 비고 |
|---|---|---|---|
| CPU 사용량 | Windows `GetSystemTimes` + `psutil` fallback | ❌ 불필요 | 플랫폼별 분기 |
| GPU 사용량 (NVIDIA) | `nvidia-ml-py` | ❌ 불필요 | NVIDIA 드라이버 필수 |
| GPU 사용량 (AMD/Intel) | Windows PDH | ❌ 불필요 | PowerShell 내장 기능 |

### 하트비트/오프라인 기준

- PC heartbeat: 60초
- PC stats 전송: 60초
- Mobile heartbeat: 60초
- 모바일에서 PC offline 판정: heartbeat 2분 초과
