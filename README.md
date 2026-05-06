# ProgressEye

> 화면 전체 공유 없이 **진행률만** 추출해 모바일로 알려주는 초경량 원격 모니터링 도구

PC에서 실행 중인 작업(렌더링, 학습, 다운로드, 게임 등)의 진행률을 OpenCV/OCR로 감지해 Firebase를 통해 모바일로 실시간 전송합니다. 90%·100% 같은 임계값 도달 시 푸시로 알리고, 모바일에서 PC로 원격 스크린샷·종료·절전 명령을 보낼 수 있습니다.

- **PC 측**: Windows 데스크톱 에이전트 (Python + PyQt6, MSIX 패키징)
- **모바일 측**: Android 앱 (Kotlin + Jetpack Compose, Material 3)
- **백엔드**: Firebase (Realtime DB + Firestore + Storage + FCM + Cloud Functions)

---

## 시스템 아키텍처

```
┌─────────────┐    진행률(%)·상태    ┌──────────────┐    FCM Push    ┌──────────────┐
│  PC Agent   │ ──────────────────▶  │   Firebase   │ ─────────────▶ │  Mobile App  │
│  (Windows)  │ ◀──────────────────  │   (Cloud)    │ ◀───────────── │  (Android)   │
└─────────────┘    원격 명령 수신     └──────────────┘  상태 조회/명령  └──────────────┘
       │                                    │                              │
       └─── Google Sign-In ─────────────────┴──────── Google Sign-In ──────┘
                              같은 계정 = 자동 연결
```

전송 데이터는 진행률 숫자(~50 bytes) 위주로 의도적으로 작게 유지해 데이터/배터리 사용량을 최소화했습니다.

---

## 진행률 감지 방식

| 모드 | 엔진 | 특징 |
|---|---|---|
| **바 탐지** | OpenCV 4-strategy + 슬라이딩 윈도우 | 그라데이션 바 지원, 픽셀 채움 비율로 산출 |
| **OCR** | RapidOCR (ONNX Runtime) | "45%" / "45" / "진행 45%완료" 등에서 숫자 추출, 적응형 이진화 fallback |

차분 전송(0.5% 이상 변화 시에만 write) · 임계값 알림(90/100% 등 사용자 정의) · 백그라운드 모니터링.

---

## 저장소 구조

```
ProgressEye/
├── pc-agent/               # Windows 데스크톱 에이전트 (Python 3.11+, PyQt6)
├── mobile-app/             # Android 앱 (Kotlin, Compose, Hilt)
│   ├── app/                # 앱 모듈
│   ├── data/               # Repository / Firebase / Room
│   ├── domain/             # UseCase / 모델 (순수 Kotlin)
│   └── build-logic/        # 컨벤션 플러그인 (composite build)
├── functions/              # Firebase Cloud Functions (Node.js 20+)
├── docs/                   # 단일 소스 공식 문서
├── database.rules.json     # Realtime DB 보안 규칙
├── firestore.rules         # Firestore 보안 규칙
└── firebase.json
```

### Android 모듈 의존 방향

```
:app  ──▶  :data  ──▶  :domain
   └──────────────────▶ :domain
```

Clean Architecture 기반의 3-모듈 구조이며, 공통 Gradle 설정은 `build-logic/convention`의 5개 컨벤션 플러그인으로 응집:

- `progeresseye.android.application` — 앱 모듈 공통(SDK 36, JDK 17, BuildConfig)
- `progeresseye.android.library` — 라이브러리 모듈 공통
- `progeresseye.android.compose` — Compose 활성화
- `progeresseye.android.hilt` — Hilt + KSP + 의존성 주입
- `progeresseye.kotlin.jvm.library` — 순수 Kotlin/JVM 라이브러리(:domain)

---

## 기술 스택

### Mobile (Android)
Kotlin 2.3.20 · AGP 9.0.1 · Jetpack Compose · Material 3 · Hilt · KSP · Coroutines · Coil 3 · Room · Navigation Compose · Firebase (Auth/RTDB/Firestore/Messaging/Crashlytics) · DataStore · Credential Manager · Play Billing 8 · Play In-App Updates · UMP(GDPR/MSPA) · AdMob · Timber

### PC Agent (Windows)
Python 3.11+ · PyQt6 · OpenCV · RapidOCR (ONNX Runtime) · Tesseract OCR · Firebase Admin SDK · Pillow · MSIX 패키징

### Backend
Firebase Realtime Database · Firestore · Cloud Storage · Cloud Functions (Node.js 20) · FCM

---

## 빌드 / 실행

### Mobile

```bash
cd mobile-app
./gradlew assembleDebug         # 디버그 APK
./gradlew :app:installDebug     # 연결된 디바이스에 설치
./gradlew publishBundle         # Play Console 자동 배포 (서비스 계정 키 필요)
```

자동 배포는 Gradle Play Publisher + 자체 `incrementVersionCode` 태스크가 `finalizedBy`로 연결돼 **단일 명령으로 빌드 → 서명 → 업로드 → 버전 증가**까지 원자적으로 수행합니다. 자세한 내용은 `docs/mobile-app/topics/build-deploy.md`.

필요한 로컬 파일(모두 gitignore됨):

| 파일 | 용도 |
|---|---|
| `mobile-app/local.properties` | Android SDK 경로 |
| `mobile-app/keystore.properties` | 릴리즈 서명 키 정보 |
| `mobile-app/app/release.jks` | 릴리즈 서명 키스토어 |
| `mobile-app/app/google-services.json` | Firebase 클라이언트 설정 |
| `mobile-app/app/google-play-api-key.json` | Play Console 서비스 계정 키 (자동 배포용) |

### PC Agent

```bash
cd pc-agent
python -m venv venv
venv\Scripts\activate           # PowerShell: venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

OAuth 토큰은 최초 실행 시 브라우저로 발급되며 `pc-agent/token.json`에 저장됩니다(gitignore됨).

### Firebase

```bash
firebase deploy --only firestore:rules,database,functions
```

---

## 보안 모델

- **인증**: Google Sign-In(Credential Manager API) + Firebase ID Token
- **권한 분리**:
  - `users/{uid}` 노드는 본인만 R/W (Firestore + RTDB 양쪽 동일)
  - `plan` / `adFreeMode` 같은 결제 플래그는 클라이언트가 변경 불가 → Cloud Functions 전용
  - 스크린샷은 Firebase Storage에 토큰 인증으로만 접근 가능
- **시크릿 외부화**: 서명 키, 서비스 계정 키, OAuth client_secret은 모두 `.gitignore`로 분리
- **광고 동의**: UMP(GDPR/EEA·MSPA/US) 지역별 자동 처리. Pro/Ad-Free 모드에서는 동의 절차 자동 스킵

자세한 내용은 `docs/security/INDEX.md`, `firestore.rules`, `database.rules.json`.

---

## 문서

`docs/INDEX.md`가 전체 문서 진입점입니다. 주요 문서:

- API/데이터 스키마: `docs/api-spec.md`
- 모바일 앱: `docs/mobile-app/INDEX.md`
- PC 에이전트: `docs/pc-agent/INDEX.md`
- 백엔드/Functions: `docs/backend/INDEX.md`
- 보안: `docs/security/INDEX.md`
- 개인정보 처리방침: `docs/privacy-policy-ko.md` · `docs/privacy-policy-en.md`

---

## 라이선스

이 저장소는 개인 포트폴리오 / 학습 목적으로 공개됩니다. 별도 라이선스가 명시되기 전까지는 코드 재사용 시 사전 협의 부탁드립니다.
