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

- `PyQt6` - GUI 프레임워크
- `mss` - 화면 캡처
- `opencv-python-headless` - 진행바 탐지 (OpenCV 4전략)
- `pytesseract` - OCR 숫자 감지
- `pystray` - 시스템 트레이
