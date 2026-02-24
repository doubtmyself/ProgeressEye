# PC Agent - 기술 설계서

---

## 1. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | OCR 생태계 풍부, 빠른 프로토타이핑 |
| GUI 프레임워크 | PyQt6 | 영역 선택 오버레이, 설정 창 구현 |
| 화면 캡처 | mss | PIL 대비 3~5배 빠른 부분 캡처 |
| OCR | Tesseract OCR (pytesseract) | 오프라인 동작, 무료, 숫자 인식 충분 |
| 이미지 전처리 | Pillow + OpenCV | 그레이스케일/이진화/노이즈 제거 |
| Firebase | firebase-admin SDK | Realtime DB 읽기/쓰기, Auth |
| 시스템 트레이 | pystray | 크로스플랫폼 트레이 아이콘 |
| 패키징 | PyInstaller | 단일 .exe 생성 |
| 설정 저장 | JSON (AppData) | 영역 좌표, 사용자 설정 영속화 |

---

## 2. 모듈 구조

```
pc-agent/
├── main.py                  # 엔트리포인트, 앱 초기화
├── config.py                # 설정 관리 (JSON 읽기/쓰기)
├── core/
│   ├── __init__.py
│   ├── capturer.py          # 화면 캡처 엔진
│   ├── ocr_engine.py        # OCR 처리 + 이미지 전처리
│   ├── freeze_detector.py   # 진행 멈춤 감지 로직
│   └── scheduler.py         # 캡처 주기 스케줄러
├── firebase/
│   ├── __init__.py
│   ├── auth.py              # 인증 및 페어링
│   ├── sync.py              # 진행률 데이터 동기화
│   └── command_listener.py  # 원격 명령 수신
├── ui/
│   ├── __init__.py
│   ├── area_selector.py     # 드래그 영역 선택 오버레이
│   ├── main_window.py       # 메인 설정/상태 창
│   ├── tray_icon.py         # 시스템 트레이
│   └── pairing_dialog.py    # 페어링 코드 표시 다이얼로그
├── utils/
│   ├── __init__.py
│   ├── logger.py            # 로깅 유틸
│   └── system_commands.py   # PC 종료/절전 명령 실행
├── resources/
│   ├── icon.ico             # 앱 아이콘
│   └── tessdata/            # Tesseract 학습 데이터
├── requirements.txt
└── build.spec               # PyInstaller 빌드 설정
```

---

## 3. 핵심 플로우

### 3.1 캡처 → OCR → 전송 사이클

```python
# 의사코드
class CaptureLoop:
    def run_cycle(self):
        # 1. 지정 영역 캡처 (메모리 내)
        screenshot = capturer.capture(region=self.selected_area)
        
        # 2. 이미지 전처리
        processed = ocr_engine.preprocess(screenshot)
        #   → grayscale → threshold → denoise
        
        # 3. OCR 숫자 추출
        result = ocr_engine.extract(processed)
        #   → { progress: 73, time_remaining: "00:42:15", confidence: 0.97 }
        
        # 4. 신뢰도 검증
        if result.confidence < THRESHOLD:
            log.warn("Low confidence, keeping previous value")
            return
        
        # 5. 멈춤 감지
        freeze_detector.update(result.progress)
        
        # 6. Firebase 전송
        firebase_sync.push(result)
```

### 3.2 영역 선택 플로우

```
1. 사용자가 "영역 선택" 클릭
2. 전체 화면 반투명 오버레이 표시
3. 마우스 드래그로 사각형 영역 지정
4. 선택 영역 하이라이트 + 미리보기 팝업
5. [확인] → 좌표 저장, 모니터링 시작
   [재선택] → 2로 복귀
   [취소] → 오버레이 닫기
```

### 3.3 OCR 이미지 전처리 파이프라인

```
원본 캡처 (RGB)
    │
    ▼
그레이스케일 변환
    │
    ▼
리사이즈 (2x~3x 확대, OCR 정확도 향상)
    │
    ▼
가우시안 블러 (노이즈 제거)
    │
    ▼
적응적 이진화 (Adaptive Threshold)
    │
    ▼
Tesseract OCR (digits + % 모드)
    │
    ▼
정규식 파싱: (\d+\.?\d*)%  |  (\d{2}:\d{2}:\d{2})
```

---

## 4. 설정 파일 구조

```json
// %APPDATA%/ProgressEye/config.json
{
  "version": 1,
  "capture": {
    "interval_seconds": 30,
    "regions": [
      {
        "id": "task_001",
        "label": "프리미어 렌더링",
        "monitor": 0,
        "x": 520, "y": 980,
        "width": 150, "height": 30
      }
    ]
  },
  "ocr": {
    "confidence_threshold": 0.8,
    "preprocess_scale": 3
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
  },
  "firebase": {
    "device_id": "pc_xxxxxxxx",
    "paired": true
  }
}
```

---

## 5. 빌드 및 배포

### 빌드 명령

```bash
# 가상환경 설정
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 단일 exe 빌드
pyinstaller build.spec
# → dist/ProgressEye.exe (약 30~50MB)
```

### PyInstaller 포함 항목

- Python 런타임
- Tesseract OCR 엔진 + 학습 데이터 (eng)
- PyQt6 라이브러리
- Firebase Admin SDK
- 앱 아이콘 및 리소스

---

## 6. 에러 처리 전략

| 상황 | 처리 |
|------|------|
| OCR 인식 실패 | 이전 값 유지, 3회 연속 실패 시 "인식 오류" 상태 전송 |
| 네트워크 끊김 | 로컬 큐에 데이터 저장, 재연결 시 일괄 전송 |
| 캡처 영역 사라짐 | 대상 창 최소화/닫힘 감지 → "대기중" 상태 전환 |
| Firebase 인증 만료 | 자동 토큰 갱신, 실패 시 재로그인 안내 |
| 메모리 부족 | 캡처 이미지 즉시 해제, 히스토리 제한 |
