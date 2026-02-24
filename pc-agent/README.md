# ProgressEye PC Agent

PC 화면의 진행바를 캡처하여 막대 픽셀 분석으로 진행률(%)을 산출하는 Windows 데스크톱 에이전트.

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