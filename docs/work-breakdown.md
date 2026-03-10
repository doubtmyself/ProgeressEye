# ProgressEye - 개발 작업 목록 (WBS)

---

## 개발 단계 개요

| 단계 | 목표 | 산출물 |
|------|------|--------|
| **1단계: MVP** | 핵심 기능 기술 검증 | Google 로그인, PC 캡처 + 막대 분석, Firebase 연동, 앱 기본 대시보드 |
| **2단계: 연동 완성** | 전체 플로우 완성 | 푸시 알림, 원격 제어, 멈춤 감지, 설정 |
| **3단계: 상용화** | 배포 준비 | .exe 패키징, Play Store, 멀티태스크, 위젯 |

---

## 1단계: MVP (기술 검증)

### PC Agent

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 1.1 | 프로젝트 초기 설정 | Python 프로젝트 구조, venv, requirements.txt | P0 | ✅ 완료 |
| 1.2 | Google OAuth 로그인 | google-auth-oauthlib 브라우저 OAuth, 토큰 발급/저장 | P0 | ✅ 완료 |
| 1.3 | 토큰 관리 | keyring 기반 토큰 안전 저장, 자동 갱신, 재로그인 | P0 | ✅ 완료 |
| 1.4 | Firebase 인증 연동 | Google credential → Firebase Auth 로그인, uid 획득 | P0 | ✅ 완료 |
| 1.5 | PC 기기 자동 등록 | 로그인 시 `users/{uid}/devices/{pcId}` 자동 등록, Presence | P0 | ✅ 완료 |
| 1.6 | 화면 영역 선택 UI | PyQt6 반투명 오버레이, 마우스 드래그 영역 지정 | P0 | ✅ 완료 |
| 1.7 | 색상 자동 감지 | 선택 영역에서 채움 색상 / 빈 색상 자동 판별, 수동 조정 UI | P0 | ✅ 완료 |
| 1.8 | 화면 캡처 모듈 | mss 기반 지정 영역 캡처, 주기적 실행 (스케줄러) | P0 | ✅ 완료 |
| 1.9 | OpenCV 바 탐지 + OCR 이중 엔진 | OpenCV 4전략 바 탐지 + 전환점 분석 + RapidOCR(ONNX Runtime) 숫자 감지 | P0 | ✅ 완료 |
| 1.10 | Firebase 데이터 전송 | `users/{uid}/devices/{pcId}/tasks/{taskId}` 에 진행률 쓰기 | P0 | ✅ 완료 |
| 1.11 | 시스템 트레이 | pystray 기반 트레이 아이콘, 기본 메뉴 (시작/정지/로그아웃/종료) | P0 | ⚠️ 제거됨 (현재 트레이 미사용) |

### Firebase (Cloud)

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 1.12 | Firebase 프로젝트 생성 | Realtime DB, Auth (Google 제공자), FCM 설정 | P0 | ✅ 완료 |
| 1.13 | Google Cloud Console 설정 | OAuth 클라이언트 ID 생성 (Desktop + Android) | P0 | ✅ 완료 |
| 1.14 | DB 스키마 초기 구성 | `users/{uid}` 하위 노드 구조 생성 | P0 | ✅ 완료 |
| 1.15 | 보안 규칙 설정 | `auth.uid == $uid` 기반 읽기/쓰기 규칙 | P0 | ✅ 완료 |
| 1.16 | onUserCreate 함수 | 신규 사용자 프로필 자동 생성, 기본 설정 초기화 | P0 | ✅ 완료 |

### Mobile App

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 1.17 | 프로젝트 초기 설정 | Kotlin + Compose 프로젝트, Hilt DI, Firebase SDK | P0 | ✅ 완료 |
| 1.18 | Google Sign-In 연동 | One Tap UI → Firebase Auth, 자동 로그인 유지 | P0 | ✅ 완료 |
| 1.19 | 로그인 화면 | Google 로그인 버튼, 인증 상태 분기 | P0 | ✅ 완료 |
| 1.20 | 테마 및 디자인 시스템 | Material Design 3 테마, 컬러/타이포 정의 | P0 | ✅ 완료 |
| 1.21 | 대시보드 화면 | PC 카드 목록, 진행률 바 표시, 실시간 업데이트 | P0 | ✅ 완료 |
| 1.22 | Empty State 화면 | PC 미등록 시 안내 ("같은 계정으로 PC Agent에서 로그인하세요") | P0 | ✅ 완료 |
| 1.23 | Firebase Realtime DB 연동 | `users/{uid}/devices` 리스너, Flow 기반 실시간 데이터 | P0 | ✅ 완료 |

### 통합 테스트

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 1.24 | E2E 검증 | Google 로그인(PC+모바일) → PC 자동 등록 → 캡처 → 막대 분석 → Firebase → 모바일 표시 | P0 | ✅ 완료 |

---

## 2단계: 연동 및 기능 완성

### PC Agent

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 2.1 | 멈춤 감지 (Freeze Detection) | 진행률 미변화 감지 → status "freeze" 전환 | P0 | ✅ 완료 |
| 2.2 | 원격 명령 수신 | `users/{uid}/commands/` SSE 리스너, screenshot/monitor ✅, shutdown/sleep ❌ | P1 | ⚠️ 부분 완료 |
| 2.3 | 명령 확인 팝업 | 명령 수신 시 사용자 확인 UI | P1 | ❌ 미구현 |
| 2.4 | 네트워크 오프라인 큐 | 연결 끊김 시 로컬 큐잉, 재연결 시 일괄 전송 | P1 | ❌ 미구현 |
| 2.5 | 설정 창 UI | 캡처 주기, 색상 허용 오차, 자동 시작, 계정 정보 | P1 | ✅ 완료 |
| 2.6 | 로그인 안내 창 | 최초 실행 시 Google 로그인 안내 UI | P1 | ✅ 완료 |

### Firebase (Cloud Functions)

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 2.7 | onTaskComplete 함수 | 완료 감지 → FCM 발송 | P0 | ✅ 완료 (onAlertCreated로 대체) |
| 2.8 | onTaskFreeze 함수 | 멈춤 감지 → FCM 발송 | P0 | ❌ 미구현 (onAlertCreated가 처리) |
| 2.9 | onDeviceOffline 함수 | PC 오프라인 → 2분 유예 후 FCM 발송 | P1 | ❌ 미구현 (onAlertCreated가 처리) |

### Mobile App

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 2.10 | FCM 푸시 알림 | 서비스 등록, 알림 채널, 알림 탭 → 상세 이동 | P0 | ✅ 완료 |
| 2.11 | 작업 상세 화면 | 개별 작업 상세 정보, 상태별 UI | P1 | ❌ 미구현 |
| 2.12 | 진행 추이 차트 | Vico 차트 연동, 시간별 진행률 그래프 | P1 | ❌ 미구현 |
| 2.13 | 원격 명령 전송 | 모니터링 시작/정지 ✅, 종료/절전 ❌ | P1 | ⚠️ 부분 완료 |
| 2.14 | 설정 화면 | 알림 설정, PC 관리, 계정 (로그아웃/전환), 테마 | P1 | ✅ 완료 |
| 2.15 | 오프라인 캐시 | 마지막 데이터 캐시, 연결 상태 표시 | P1 | ❌ 미구현 |

---

## 3단계: 상용화 패키징

### PC Agent

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 3.1 | PyInstaller 빌드 | 단일 .exe 패키징 | P1 | ✅ 완료 (Nuitka로 변경) |
| 3.2 | Windows 시작프로그램 등록 | 자동 시작 옵션 구현 | P1 | ❌ 미구현 |
| 3.3 | 멀티 모니터 지원 | 다중 모니터 영역 선택 | P2 | ✅ 완료 |
| 3.4 | 멀티 태스크 모니터링 | 동시 5개 영역 모니터링 | P2 | ✅ 완료 |
| 3.5 | 자동 업데이트 | 새 버전 확인 및 업데이트 | P2 | ✅ 완료 (강제 버전 체크) |

### Mobile App

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 3.6 | 홈 위젯 | Glance 기반 진행률 위젯 | P2 | ❌ 미구현 |
| 3.7 | 다국어 지원 | 한국어/영어 strings 분리 (values-ko/strings.xml) | P2 | ✅ 완료 |
| 3.8 | Play Store 준비 | 스토어 등록 정보, 스크린샷, 설명 | P1 | ✅ 완료 (GPP 설정 완료) |
| 3.9 | 성능 최적화 | 배터리/데이터 최적화 검증 | P1 | ❌ 미구현 |

### 공통

| # | 작업 | 설명 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 3.10 | CI/CD 파이프라인 | GitHub Actions: 린트, 테스트, 빌드 자동화 | P1 | ❌ 미구현 |
| 3.11 | 에러 모니터링 | Firebase Crashlytics (모바일), Sentry (PC) | P2 | ❌ 미구현 |

---

## 추가 구현 사항 (설계 이후 추가)

| # | 작업 | 설명 | 상태 |
|---|------|------|------|
| A.1 | 회원 탈퇴 | 모바일에서 계정 삭제: forceLogout → RTDB 삭제 → Auth 삭제 → signOut | ✅ 완료 |
| A.2 | forceLogout 명령 | PC Agent SSE로 forceLogout 수신 → 로그아웃 + 앱 종료 | ✅ 완료 |
| A.3 | 완료 지연 시간 | 작업별 alert_delay_minutes 설정, 완료 게이지 N분 유지 확인 | ✅ 완료 |
| A.4 | 강제 버전 체크 | Firestore appConfig/pc에서 minVersion 조회, 로그인 전 체크 | ✅ 완료 |
| A.5 | Firestore 마이그레이션 | plan 정보 RTDB → Firestore users/{uid} 이동 | ✅ 완료 |
| A.6 | FCM notification 필드 | Cloud Function에 notification: { title, body } 추가 | ✅ 완료 |
| A.7 | 알림 런타임 권한 | Android 13+ POST_NOTIFICATIONS 권한 요청 | ✅ 완료 |
| A.8 | 모니터링 파이프라인 리팩토링 | 모니터링 중 bar_finder 제거, bar_analyzer만 사용 | ✅ 완료 |
| A.9 | 다이얼로그 닫기 버그 수정 | BarPreviewDialog/OcrPreviewDialog 닫을 때 영역 재선택 방지 | ✅ 완료 |
| A.10 | 자동 배포 (Android) | GPP 4.0.0, R8 난독화, version.properties 자동 증가 | ✅ 완료 |
| A.11 | 개인정보처리방침 | Firebase Hosting에 계정 삭제 안내 추가 | ✅ 완료 |
| A.12 | MSIX 패키징 (PC) | Nuitka 빌드 + MSIX 패키지, Microsoft Store 배포 | ✅ 완료 |
| A.13 | RapidOCR 엔진 마이그레이션 | pytesseract → RapidOCR(ONNX Runtime). lazy threshold fallback, 디버그 OCR 크롭 저장 | ✅ 완료 |
| A.14 | 분석 병렬 처리 | ThreadPoolExecutor(max_workers=CPU코어수), 영역별 중복 실행 스킵 가드 | ✅ 완료 |
| A.15 | 작업 상태 시스템 | running/completed/stopped 상태, 모든 작업 종료 시 모니터링 자동 중단, PC카드+모바일 표시 | ✅ 완료 |
| A.16 | RegionEditor 바 탐지 미리보기 | 바 영역 재선택 시 RegionEditor 오버레이 + 선택 영역 내 바 탐지 결과 빨간 사각형 표시 | ✅ 완료 |
| A.17 | HW 통계 즉시 표시 | CPU/GPU/RAM 샘플러를 앱 시작 5초 후 자동 시작 (Firebase 로그인 불필요) | ✅ 완료 |

---

## 작업 의존성 그래프

```
[1단계 MVP]
  1.12 ─→ 1.13 ─→ 1.15 ─→ 1.16 ──────────────────────── (Firebase 기반)
                     │
  1.1 ──→ 1.2 ──→ 1.3 ──→ 1.4 ──→ 1.5 ──→ 1.6 ──→ 1.7 ──→ 1.8 ──→ 1.9 ──→ 1.10 ──→ 1.24
                     │                                                                    │
  1.17 ─→ 1.18 ─→ 1.19 ─→ 1.20 ─→ 1.21 ─→ 1.22 ─→ 1.23 ──────────────────────────────┘

[2단계 연동]
  2.1 ──→ 2.8 ──────────────────→ 2.10 (멈춤 알림)
  2.7 ────────────────────────────→ 2.10 (완료 알림)
  2.2 ──→ 2.3 ──────────────────→ 2.13 (원격 제어)

[3단계 상용화]
  3.1, 3.8 은 독립 작업 가능
  3.6 은 2.10 완료 후
```

---

## 이전 설계 대비 변경 사항 (누적)

| 항목 | 최초 설계 | 현재 설계 |
|------|-----------|-----------|
| 인증 | 익명 인증 + 6자리 페어링 코드 | **Google OAuth 2.0** |
| 연결 | pairs/ + links/ 노드 | **같은 uid = 자동 연결** |
| 감지 방식 | Tesseract OCR 숫자 인식 | **바 탐지(OpenCV) + OCR(RapidOCR ONNX) 이중 모드** |
| DB 구조 | 최상위에 분산 | **`users/{uid}/` 아래 통합** |
| 외부 의존성 | Tesseract OCR 번들 (30MB+) | **바 탐지: opencv-python-headless, OCR: rapidocr-onnxruntime** |
| exe 크기 | ~50MB | **~30MB (바 탐지 + RapidOCR ONNX 포함)** |
| 범용성 | 숫자 텍스트 있는 진행바만 | **텍스트 없는 진행바도 지원, 숫자 있으면 OCR도 사용 가능** |
| 삭제된 항목 | 페어링 코드, cleanupExpiredPairs | — |
| UI 테마 | 기본 OS 스타일 | **다크 테마 (#0f0f1a 배경, 커스텀 색상 팔레트)** |
| OCR 매칭 | fullmatch (정확 일치만) | **search (앞뒤 문자 포함 감지)** |
| 추가된 항목 | — | 바 탐지 엔진(OpenCV), OCR 엔진(RapidOCR), 색상 감지, Google Auth, onUserCreate, 병렬 분석, 작업 상태 시스템, RegionEditor |
| Firebase 연동 | firebase-admin SDK | **Firebase REST API (requests)** |
| 인증 토큰 교환 | 미정 | **Google OAuth → signInWithIdp REST API → keyring 저장** |
| 패키징 (PC) | PyInstaller (.exe) | **Nuitka (네이티브 C 컴파일) + MSIX** |
| 패키징 (Mobile) | 수동 빌드 | **Gradle Play Publisher (GPP) 자동 배포** |
| plan 저장소 | Realtime Database | **Firestore users/{uid}** |
| Cloud Functions | onTaskComplete, onTaskFreeze, onDeviceOffline, onUserCreate | **onAlertCreated (alerts 트리거 → FCM, 1개만 구현)** |
| 명령 구조 | commands/{pcId}/{type} | **commands/{type} (flat 구조)** |
| 알림 구조 | settings/notifications | **alerts/{alertId} + fcmTokens/{tokenId}** |
| 회원 탈퇴 | 미구현 | **모바일에서 삭제: forceLogout → RTDB 삭제 → Auth 삭제** |
| 모니터링 | bar_finder 매 사이클 | **영역 선택 시에만 bar_finder, 모니터링 중 bar_analyzer만** |

---

## 우선순위 정의

| 레벨 | 의미 | 기준 |
|------|------|------|
| **P0** | 필수 | MVP에 반드시 포함. 없으면 제품 의미 없음 |
| **P1** | 중요 | 2단계 완료 시 포함. 사용성에 직접 영향 |
| **P2** | 추가 | 있으면 좋지만 없어도 핵심 기능 동작 |
