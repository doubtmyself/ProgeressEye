# PC Agent - 기술 설계서

---

## 1. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | 이미지 처리 생태계 풍부, 빠른 프로토타이핑 |
| GUI 프레임워크 | PyQt6 | 영역 선택 오버레이, 설정 창 구현 |
| 화면 캡처 | mss | PIL 대비 3~5배 빠른 부분 캡처, thread-local GDI |
| 바 탐지 | opencv-python-headless | OpenCV 4전략 기반 진행바 자동 탐지 |
| OCR 감지 | pytesseract + Tesseract OCR | 숫자가 보이는 진행바에서 % 수치 직접 인식 |
| 인증 | google-auth + google-auth-oauthlib | 브라우저 기반 Google OAuth 2.0 |
| Firebase | requests (Firebase REST API) | Realtime DB 읽기/쓰기 (`{DB_URL}/{path}.json?auth={idToken}`), firebase-admin은 서버용이므로 데스크톱 클라이언트에서는 REST API 직접 호출 |
| 시스템 트레이 | pystray | 크로스플랫폼 트레이 아이콘 (queue.Queue + QTimer 폴링) |
| 패키징 | PyInstaller | 단일 .exe 생성 |
| 설정 저장 | JSON (AppData) | 영역 좌표, 색상, 사용자 설정 영속화 |
| 토큰 저장 | keyring | OS 자격증명 저장소에 안전하게 토큰 보관 |

> **이중 감지 모드**: 진행바 픽셀 분석(OpenCV)과 OCR 숫자 감지(pytesseract) 두 가지 모드를 지원한다. 숫자가 화면에 표시되는 경우 OCR 모드를, 그렇지 않은 경우 바 탐지 모드를 사용한다.

---

## 2. 모듈 구조

```
pc-agent/
├── main.py                  # 엔트리포인트, 앱 초기화 + 인증 통합 + Firebase 연동
├── config.py                # 설정 관리 (JSON)
├── setup_tesseract.py       # Tesseract OCR 번들 설치 스크립트
├── auth/
│   ├── google_oauth.py      # InstalledAppFlow.run_local_server(port=8080)으로 브라우저 팝업 → id_token 획득
│   ├── firebase_auth.py     # Firebase REST API (signInWithIdp + refresh_token)로 Firebase 로그인
│   └── token_manager.py     # keyring으로 Windows 자격증명 저장소에 토큰 보관, 자동 갱신
├── firebase/
│   ├── realtime_db.py       # RealtimeDB 클래스, REST API 래퍼 (get/put/patch/delete)
│   └── device_manager.py    # DeviceManager 클래스, 기기 등록/상태/하트비트/오프라인
├── core/
│   ├── bar_finder.py        # OpenCV 4전략 바 탐지 + Sobel 트랙 확장
│   ├── bar_analyzer.py      # 전환점 분석 (그라데이션 지원)
│   ├── ocr_reader.py        # pytesseract 기반 숫자% 탐지 (단독 숫자 포함)
│   ├── capturer.py          # mss 기반 화면 캡처 (thread-local GDI)
│   ├── freeze_detector.py   # 진행 멈춤 감지
│   └── scheduler.py         # Timer 기반 주기 캡처
├── ui/
│   ├── main_window.py       # 메인 창 (다크 테마, 색상 팔레트 27개 상수)
│   ├── area_selector.py     # 드래그 영역 선택 오버레이
│   ├── color_picker.py      # InteractiveBarPreview + BarPreviewDialog
│   ├── ocr_preview.py       # OCR 탐지 미리보기 (빨간+시안 사각형)
│   ├── region_viewer.py     # 전체 화면 탐지 결과 오버레이
│   └── tray_icon.py         # 시스템 트레이 (간소화)
├── tesseract/               # Tesseract OCR 번들 (바이너리, .gitignore)
│   ├── tesseract.exe
│   ├── *.dll
│   └── tessdata/eng.traineddata, osd.traineddata
├── utils/
│   └── logger.py
└── resources/
    └── icon.ico
```

---

## 3. 핵심 플로우

### 3.1 앱 시작 → 인증 플로우

```
앱 시작
  │
  ├─ keyring에 저장된 토큰 있음 ──→ refresh_token으로 Firebase 자동 로그인 (_try_auto_login)
  │                          │
  │                          ├─ 성공 ──→ Firebase 초기화 (기기 등록 + 프로필 저장 + 30초 하트비트)
  │                          └─ 실패 ──→ 수동 로그인 다이얼로그 (_ensure_login)
  │
  └─ 토큰 없음 ──→ 수동 로그인 다이얼로그 (Retry/Cancel)
                 │
                 └─ Google OAuth (InstalledAppFlow.run_local_server(port=8080))
                       │
                       └─ id_token → signInWithIdp REST API → Firebase uid 획득
                             │
                             └─ keyring 저장 → Firebase 초기화 → 메인 화면
```

### 3.2 영역 선택 → 모드 분기 → 탐지 → 등록 플로우

```
메인 화면
  │
  ├─ [프로그래스바 영역 추가] ──→ 드래그 영역 선택
  │                                  │
  │                                  ▼
  │                            OpenCV 바 탐지 (4전략)
  │                                  │
  │                                  ▼
  │                            InteractiveBarPreview
  │                            (파워포인트식 리사이즈 핸들)
  │                                  │
  │                                  ▼
  │                            [확인] → "진행률 바" 배지로 등록
  │
  └─ [숫자 영역 추가] ──→ 드래그 영역 선택
                             │
                             ▼
                       OCR 탐지 미리보기
                       (빨간+시안 사각형으로 감지 결과 표시)
                             │
                             ▼
                       [확인] → "진행률 퍼센트" 배지로 등록
```

### 3.2 바 탐지 파이프라인 (OpenCV 4전략)

```python
# 의사코드
class BarFinder:
    def find(self, image):
        """
        OpenCV 4전략으로 진행바 후보 영역을 탐지한다.
        
        전략 1: Canny + Otsu 엣지 기반 탐지
        전략 2: 적응형 이진화 (Adaptive Threshold)
        전략 3: HSV 채도 분할 (색상 있는 바 탐지)
        전략 4: 배경 제거 (배경색과 다른 영역 추출)
        
        각 전략의 결과를 앙상블하여 최종 바 영역 반환.
        Sobel 트랙 확장으로 바 경계를 정밀하게 보정.
        """
        candidates = []
        candidates += self._canny_otsu(image)
        candidates += self._adaptive_threshold(image)
        candidates += self._hsv_saturation(image)
        candidates += self._background_removal(image)
        
        return self._ensemble(candidates)
```

### 3.3 바 분석 엔진 (전환점 분석)

```python
# 의사코드
class BarAnalyzer:
    def analyze(self, image):
        """
        진행바 이미지에서 채움 비율을 계산한다.
        
        원리:
        1. 슬라이딩 윈도우로 열(column)별 색상 변화를 추적
        2. 채움 영역에서 빈 영역으로 전환되는 지점(전환점) 탐지
        3. 그라데이션 진행바도 지원 (색상 연속 변화 허용)
        4. 전환점 위치 / 전체 너비 = 진행률(%)
        """
        pixels = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        transition_point = self._find_transition(pixels)
        progress = (transition_point / image.shape[1]) * 100
        return round(progress, 1)
```

### 3.4 OCR 탐지 파이프라인 (pytesseract)

```python
# 의사코드
class OcrReader:
    def read(self, image):
        """
        pytesseract로 진행률 숫자를 인식한다.
        
        인식 패턴:
        - "45%" 형태: % 기호와 함께 인식
        - "45" + "%" 분리 인식: 두 요소가 근접한 경우 합산
        - 단독 숫자 "45": % 없이 0~100 범위의 숫자만 있어도 감지
        - 앞뒤 문자 포함 텍스트에서도 추출 (search 매칭)
        
        신뢰도 기반 필터링으로 오인식 최소화.
        """
        text = pytesseract.image_to_string(image, config='--psm 7')
        return self._parse_percentage(text)
    
    def _parse_percentage(self, text):
        # "45%", "45 %", 단독 "45" (0~100 범위), "진행르45%완료" 등 모두 처리
        ...
```

### 3.5 영역 선택 플로우

```
1. 사용자가 "프로그래스바 영역 추가" 또는 "숫자 영역 추가" 클릭
2. 전체 화면 반투명 오버레이 표시 (멀티모니터 지원, mss 좌표 ↔ Qt 좌표 변환)
3. 마우스 드래그로 사각형 영역 지정
4. 모드에 따라 미리보기 표시:
   - 바 탐지 모드: InteractiveBarPreview (파워포인트식 리사이즈 핸들로 영역 편집 가능)
   - OCR 모드: OcrPreview (빨간+시안 사각형으로 감지된 숫자 위치 표시)
5. [확인] → 좌표 + 모드 저장, 모니터링 시작
   [재선택] → 2로 복귀
   [취소] → 오버레이 닫기
```

---

## 4. 설정 파일 구조

```json
// %APPDATA%/ProgressEye/config.json
{
  "version": 2,
  "auth": {
    "uid": "firebase_uid_xxx",
    "email": "user@gmail.com",
    "device_id": "pc_a1b2c3d4",
    "device_name": "작업용 PC"
  },
  "capture": {
    "interval_seconds": 30,
    "regions": [
      {
        "id": "task_001",
        "label": "프리미어 렌더링",
        "type": "bar",
        "monitor": 0,
        "x": 520, "y": 980,
        "width": 300, "height": 20,
        "fill_color": [66, 133, 244],
        "empty_color": [224, 224, 224],
        "color_tolerance": 30,
        "direction": "left_to_right"
      },
      {
        "id": "task_002",
        "label": "Blender 렌더링",
        "type": "ocr",
        "monitor": 0,
        "x": 800, "y": 600,
        "width": 80, "height": 24
      }
    ]
  },
  "analysis": {
    "confidence_threshold": 0.8
  },
  "freeze_detection": {
    "enabled": true,
    "timeout_minutes": 5
  },
  "remote_command": {
    "require_confirmation": true
  },
  "startup": {
    "auto_start": false,
    "start_minimized": true
  }
}
```

> **Note**: Google OAuth 토큰은 `config.json`에 저장하지 않고, `keyring` 라이브러리를 통해 **Windows 자격 증명 관리자**에 안전하게 보관한다.

---

## 5. 빌드 및 배포

### 빌드 명령

```bash
# 가상환경 설정
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Tesseract 번들 설치 (OCR 모드 포함 빌드 시)
python setup_tesseract.py

# 단일 exe 빌드
pyinstaller build.spec
# → dist/ProgressEye.exe
#   Tesseract 번들 포함: 약 160MB
#   Tesseract 번들 미포함: 약 15MB
```

### PyInstaller 포함 항목

- Python 런타임
- PyQt6 라이브러리
- opencv-python-headless (바 탐지)
- pytesseract (OCR 인터페이스)
- Google Auth + requests 라이브러리 (google-auth, google-auth-oauthlib, requests, keyring)
- Google OAuth 클라이언트 설정 (client_secret.json)
- 앱 아이콘 및 리소스
- tesseract/ 폴더 (Tesseract 바이너리 + tessdata, 번들 포함 시)

---

## 6. 에러 처리 전략

| 상황 | 처리 |
|------|------|
| Google 로그인 실패 | 에러 메시지 표시, 재시도 안내 |
| 토큰 갱신 실패 | 자동 재로그인 시도, 실패 시 로그인 화면 표시 |
| 바 탐지 실패 | 4전략 모두 실패 시 수동 색상 지정 안내 |
| OCR 인식 실패 | Tesseract 미설치 안내 또는 이전 값 유지 |
| 분석 신뢰도 낮음 | 이전 값 유지, 3회 연속 시 "분석 오류" 상태 전송 |
| 네트워크 끊김 | 로컬 큐에 데이터 저장, 재연결 시 일괄 전송 |
| 캡처 영역 사라짐 | 대상 창 최소화/닫힘 감지 → "대기중" 상태 전환 |
| Firebase 연결 끊김 | 자동 재연결, 오프라인 큐잉 |
| 메모리 부족 | 캡처 이미지 즉시 해제, 히스토리 제한 |
