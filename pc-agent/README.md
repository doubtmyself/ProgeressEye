# ProgressEye PC Agent

PC 화면의 진행바를 캡처하여 **진행바 픽셀 분석(OpenCV)** 또는 **OCR 숫자 감지(pytesseract)** 두 가지 모드로 진행률(%)을 산출하는 Windows 데스크톱 에이전트.

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
- `mss` - 화면 캡처
- `opencv-python-headless` - 진행바 탐지 (OpenCV 4전략)
- `pytesseract` - OCR 숫자 감지
- `pystray` - 시스템 트레이
- `google-auth` - Google OAuth 토큰 검증
- `google-auth-oauthlib` - 브라우저 기반 Google OAuth 2.0 로그인
- `requests` - Firebase REST API 호출
- `keyring` - Windows 자격증명 관리자에 토큰 안전 저장
- `UI 테마` - 다크 테마 (커스텀 색상 팔레트)
## Google OAuth 설정

최초 실행 전 Google Cloud Console에서 발급한 OAuth 클라이언트 설정 파일이 필요하다.

1. [Google Cloud Console](https://console.cloud.google.com/)에서 OAuth 2.0 클라이언트 ID 생성 (데스크톱 앱 유형)
2. 다운로드한 JSON 파일을 `pc-agent/client_secret.json`으로 저장
3. 앱 실행 시 브라우저가 열리며 Google 로그인 진행 → `localhost:8080`으로 리다이렉트되어 토큰 수신
4. 이후 실행부터는 keyring에 저장된 토큰으로 자동 로그인

## Firebase 연동

- 인증: Google OAuth `id_token`을 Firebase REST API (`signInWithIdp`)로 교환하여 Firebase uid 획득
- 데이터 전송: `requests` 라이브러리로 Firebase Realtime DB REST API 직접 호출
  - 경로: `{DB_URL}/{path}.json?auth={idToken}`
- 토큰 갱신: `refresh_token`으로 자동 갱신 (만료 1시간)
- 기기 등록: 로그인 성공 시 `users/{uid}/devices/{pcId}` 자동 등록
- 하트비트: 30초마다 `lastSeen` 갱신
- 종료 시: `status: offline` 기록
