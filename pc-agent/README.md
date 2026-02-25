# ProgressEye PC Agent

PC 화면의 진행바를 캐콉하여 **진행바 픽셀 분석(OpenCV)** 또는 **OCR 숫자 감지(pytesseract)** 두 가지 모드로 진행률(%)을 산출하는 Windows 데스크톱 에이전트.

## 실행 방법

```bash
cd C:\ProgressEye\pc-agent
venv\Scripts\python.exe main.py
```

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

- `mss` — 화면 캐콉
- `opencv-python-headless` — 진행바 탐지 (OpenCV 4전략)
- `pytesseract` — OCR 숫자 감지
- `pystray` — 시스템 트레이
- `google-auth` / `google-auth-oauthlib` — Google OAuth 2.0 로그인
- `requests` — Firebase REST API 호출
- `keyring` — Windows 자격증명 관리자에 토큰 안전 저장
- `PyQt6` — UI 프레임워크 (다크 테마)

## 성능 최적화

### 바 모드 — Smart 다운스케일

진행바 픽셀 분석 시 50% 다운스케일을 적용하여 OpenCV 연산량을 ~75% 감소시킨다.
신뢰도가 낮을 때(얀은 바, 복잡한 오버레이) 원본 해상도로 자동 fallback한다.

| 단계 | 설명 |
|---|---|
| 1. 다운스케일 시도 | 50% 축소 후 bar_finder + bar_analyzer 실행 |
| 2. 신뢰도 검증 | confidence < 0.5 또는 uniform bar 의심(0%/100% + conf ≤ 0.7) |
| 3. Fallback | 조건 충족 시 원본 해상도로 재분석 |

- 샘플 테스트 결과: 최대 오차 1.0% (Smart) vs 66.0% (단순 50%)
- 속도: 1.5~2.5배 빠름 (일반 이미지), fallback 시 원본과 동등

### OCR 모드 — 변화 감지 + LSTM-only

OCR 모드에서는 두 가지 최적화를 적용한다:

**1. 변화 감지 (Change Detection)**
- 이전 캐콉과 픽셀을 비교하여 변화가 없으면 OCR을 스킵하고 캐시된 결과를 반환
- 이미지를 32x32로 축소 후 MD5 해싱으로 빠른 비교
- 효과: OCR 실행 72~107ms → skip 시 0.1~2ms (**50~500배 절약**)

**2. Tesseract 설정 최적화**
- `--oem 1` (LSTM only): Legacy+LSTM 대비 가벼움
- `--psm 6` (블록 모드): 다양한 레이아웃 호환성 유지
- 숫자+% 필터링은 regex로 처리 (화면 캐콉에 비숫자 요소 포함 가능)

### 저사양 PC 예상 점유율 (2코어 Celeron, 4GB RAM)

| 시나리오 | CPU 평균 | 메모리 |
|---|---|---|
| 유휴 (대기) | ~0.5% | ~80~100MB |
| 바 모드 30초 주기 | ~2~4% | ~120~150MB |
| OCR 모드 30초 주기 (변화 없으면 skip) | ~0.5~1% | ~130~170MB |
| 바 모드 1초 주기 | ~10~15% | ~130MB |

## UI/설정

- **다크 테마**: 커스텀 색상 팔레트 (`#0f0f1a` ~ `#3b82f6`)
- **설정 오버레이**: MainWindow 내부 모달 (모니터링 간격, 언어, 계정 정보, 로그아웃)
- **다국어**: 한국어 / 영어 (i18n 모듈)
- **로그아웃**: 토큰 삭제 → 앱 종료
- **시스템 트레이**: 최소화 시 트레이 상주

## Google OAuth 설정

최초 실행 전 Google Cloud Console에서 발급한 OAuth 클라이언트 설정 파일이 필요하다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
2. 다운로드한 JSON 파일을 `pc-agent/client_secret.json`으로 저장
3. 앱 실행 시 OS 기본 브라우저가 열리며 Google 로그인 진행 → `localhost:8080`으로 리다이렉트되어 토큰 수신
4. 이후 실행부터는 keyring에 저장된 토큰으로 자동 로그인

## Firebase 연동

- 인증: Google OAuth `id_token`을 Firebase REST API (`signInWithIdp`)로 교환하여 Firebase uid 획득
- 데이터 전송: `requests` 라이브러리로 Firebase Realtime DB REST API 직접 호출
  - 경로: `{DB_URL}/{path}.json?auth={idToken}`
- 토큰 갱신: `refresh_token`으로 자동 갱신 (만료 1시간)
- 기기 등록: 로그인 성공 시 `users/{uid}/devices/{pcId}` 자동 등록
- 하트비트: 30초마다 `lastSeen` 갱신
- 종료 시: `status: offline` 기록
