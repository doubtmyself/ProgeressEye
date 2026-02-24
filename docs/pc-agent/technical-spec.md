# PC Agent - 기술 설계서

---

## 1. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Python 3.11+ | 이미지 처리 생태계 풍부, 빠른 프로토타이핑 |
| GUI 프레임워크 | PyQt6 | 영역 선택 오버레이, 설정 창 구현 |
| 화면 캡처 | mss | PIL 대비 3~5배 빠른 부분 캡처 |
| 이미지 분석 | Pillow + NumPy | 픽셀 색상 분석, 채움 비율 계산 |
| 인증 | google-auth + google-auth-oauthlib | 브라우저 기반 Google OAuth 2.0 |
| Firebase | firebase-admin SDK | Realtime DB 읽기/쓰기, Auth |
| 시스템 트레이 | pystray | 크로스플랫폼 트레이 아이콘 |
| 패키징 | PyInstaller | 단일 .exe 생성 |
| 설정 저장 | JSON (AppData) | 영역 좌표, 색상, 사용자 설정 영속화 |
| 토큰 저장 | keyring | OS 자격증명 저장소에 안전하게 토큰 보관 |

> **Tesseract OCR 제거**: 막대 픽셀 분석 방식 채택으로 OCR 엔진 불필요. exe 크기 30MB+ 절감.

---

## 2. 모듈 구조

```
pc-agent/
├── main.py                  # 엔트리포인트, 앱 초기화
├── config.py                # 설정 관리 (JSON 읽기/쓰기)
├── core/
│   ├── __init__.py
│   ├── capturer.py          # 화면 캡처 엔진
│   ├── bar_analyzer.py      # 진행바 막대 픽셀 분석 엔진
│   ├── color_detector.py    # 채움/빈 색상 자동 감지
│   ├── freeze_detector.py   # 진행 멈춤 감지 로직
│   └── scheduler.py         # 캡처 주기 스케줄러
├── auth/
│   ├── __init__.py
│   ├── google_auth.py       # Google OAuth 2.0 브라우저 로그인
│   └── token_manager.py     # 토큰 저장/갱신/만료 관리
├── firebase/
│   ├── __init__.py
│   ├── client.py            # Firebase 초기화 + 인증 연동
│   ├── sync.py              # 진행률 데이터 동기화
│   ├── device_register.py   # PC 기기 등록 + Presence 관리
│   └── command_listener.py  # 원격 명령 수신
├── ui/
│   ├── __init__.py
│   ├── login_window.py      # Google 로그인 안내 창
│   ├── area_selector.py     # 드래그 영역 선택 오버레이
│   ├── color_picker.py      # 채움/빈 색상 미리보기 및 수동 조정
│   ├── main_window.py       # 메인 설정/상태 창
│   └── tray_icon.py         # 시스템 트레이
├── utils/
│   ├── __init__.py
│   ├── logger.py            # 로깅 유틸
│   └── system_commands.py   # PC 종료/절전 명령 실행
├── resources/
│   ├── icon.ico             # 앱 아이콘
│   └── client_secret.json   # Google OAuth 클라이언트 설정
├── requirements.txt
└── build.spec               # PyInstaller 빌드 설정
```

---

## 3. 핵심 플로우

### 3.1 앱 시작 → 인증 플로우

```
앱 시작
  │
  ├─ 저장된 토큰 있음 ──→ 토큰 유효성 검증
  │                          │
  │                          ├─ 유효 ──→ 자동 로그인 ──→ 메인 화면
  │                          └─ 만료 ──→ 자동 갱신 ──→ 메인 화면
  │                                        │
  │                                        └─ 갱신 실패 ──→ 로그인 화면
  │
  └─ 토큰 없음 ──→ 로그인 화면 ──→ Google 로그인 ──→ 메인 화면
```

### 3.2 캡처 → 막대 분석 → 전송 사이클

```python
# 의사코드
class CaptureLoop:
    def run_cycle(self):
        # 1. 지정 영역 캡처 (메모리 내)
        screenshot = capturer.capture(region=self.selected_area)
        
        # 2. 막대 픽셀 분석
        result = bar_analyzer.analyze(
            image=screenshot,
            fill_color=self.fill_color,      # 채움 색상 (RGB)
            empty_color=self.empty_color,    # 빈 색상 (RGB)
            tolerance=self.color_tolerance   # 색상 허용 오차
        )
        #   → { progress: 73.2, confidence: 0.95 }
        
        # 3. 신뢰도 검증
        if result.confidence < THRESHOLD:
            log.warn("Low confidence, keeping previous value")
            return
        
        # 4. 멈춤 감지
        freeze_detector.update(result.progress)
        
        # 5. Firebase 전송 (users/{uid}/tasks/{pcId}/{taskId})
        firebase_sync.push(uid=self.uid, pc_id=self.pc_id, result=result)
```

### 3.3 막대 픽셀 분석 엔진 상세

```python
# 의사코드
class BarAnalyzer:
    def analyze(self, image, fill_color, empty_color, tolerance=30):
        """
        진행바 이미지에서 채움 비율을 계산한다.
        
        원리:
        1. 이미지의 각 열(column)에 대해 평균 색상을 구함
        2. 평균 색상이 fill_color에 가까우면 "채움"
        3. 평균 색상이 empty_color에 가까우면 "빈"
        4. 채운 열 수 / 전체 열 수 = 진행률
        """
        pixels = np.array(image)       # (height, width, 3)
        column_means = pixels.mean(axis=0)  # (width, 3) — 열별 평균색
        
        fill_distances = color_distance(column_means, fill_color)
        empty_distances = color_distance(column_means, empty_color)
        
        # 각 열이 채움인지 빈인지 판정
        is_filled = fill_distances < empty_distances
        
        # 좌→우 진행 방향: 첫 번째 빈 열의 위치가 진행 경계
        if is_filled.any():
            # 연속된 채움 영역의 끝 찾기
            filled_count = np.argmin(is_filled) if not is_filled.all() else len(is_filled)
        else:
            filled_count = 0
        
        total_columns = len(is_filled)
        progress = (filled_count / total_columns) * 100
        
        # 신뢰도: 채움/빈 색상이 얼마나 명확하게 구분되는지
        confidence = calculate_confidence(fill_distances, empty_distances)
        
        return AnalysisResult(progress=round(progress, 1), confidence=confidence)
```

### 3.4 색상 자동 감지 플로우

```
영역 선택 완료
  │
  ▼
캡처 이미지 분석
  │
  ├─ 좌측 1/4 영역의 주요 색상 → 채움 색상 후보
  ├─ 우측 1/4 영역의 주요 색상 → 빈 색상 후보
  │
  ▼
미리보기 팝업
  │
  ├─ "채움 색상: ██ #4285F4"
  ├─ "빈 색상:   ██ #E0E0E0"
  ├─ "감지된 진행률: 73%"
  │
  ├─ [확인] → 색상 저장, 모니터링 시작
  ├─ [색상 수동 조정] → 컬러 피커 표시
  └─ [재선택] → 영역 선택으로 복귀
```

### 3.5 영역 선택 플로우

```
1. 사용자가 "영역 선택" 클릭
2. 전체 화면 반투명 오버레이 표시
3. 마우스 드래그로 사각형 영역 지정
4. 선택 영역 하이라이트 + 색상 자동 감지
5. 미리보기: 감지된 채움/빈 색상 + 현재 진행률 표시
6. [확인] → 좌표 + 색상 저장, 모니터링 시작
   [색상 조정] → 컬러 피커로 수동 지정
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
        "monitor": 0,
        "x": 520, "y": 980,
        "width": 300, "height": 20,
        "fill_color": [66, 133, 244],
        "empty_color": [224, 224, 224],
        "color_tolerance": 30,
        "direction": "left_to_right"
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

# 단일 exe 빌드
pyinstaller build.spec
# → dist/ProgressEye.exe (약 15MB — Tesseract 불포함)
```

### PyInstaller 포함 항목

- Python 런타임
- PyQt6 라이브러리
- Pillow + NumPy (이미지 분석)
- Firebase Admin SDK + Google Auth 라이브러리
- Google OAuth 클라이언트 설정 (client_secret.json)
- 앱 아이콘 및 리소스

> **이전 대비 제거**: Tesseract OCR 엔진 + tessdata 학습 데이터 (~30MB 절감)

---

## 6. 에러 처리 전략

| 상황 | 처리 |
|------|------|
| Google 로그인 실패 | 에러 메시지 표시, 재시도 안내 |
| 토큰 갱신 실패 | 자동 재로그인 시도, 실패 시 로그인 화면 표시 |
| 색상 감지 실패 | 수동 색상 지정 안내, 컬러 피커 표시 |
| 분석 신뢰도 낮음 | 이전 값 유지, 3회 연속 시 "분석 오류" 상태 전송 |
| 네트워크 끊김 | 로컬 큐에 데이터 저장, 재연결 시 일괄 전송 |
| 캡처 영역 사라짐 | 대상 창 최소화/닫힘 감지 → "대기중" 상태 전환 |
| Firebase 연결 끊김 | 자동 재연결, 오프라인 큐잉 |
| 메모리 부족 | 캡처 이미지 즉시 해제, 히스토리 제한 |
