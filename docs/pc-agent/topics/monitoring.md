# PC 모니터링/감지

## 목적
영역 선택부터 진행률 산출(바/OCR)까지의 핵심 파이프라인을 찾는다.

## 핵심 코드
- `pc-agent/ui/area_selector.py`
- `pc-agent/core/capturer.py`
- `pc-agent/core/bar_finder.py`
- `pc-agent/core/bar_analyzer.py`
- `pc-agent/core/ocr_reader.py`
- `pc-agent/main.py`

## 확인 포인트
- 영역 등록 시 bar 탐지, 운영 중 analyzer 중심 경로
- OCR 모드 숫자 파싱 규칙
- 멀티모니터 좌표 변환: `pc-agent/ui/screen_mapper.py`

## 관련 문서
- 요구사항: `docs/pc-agent/requirements.md` (FR-PC-002~005)
- 기술설계: `docs/pc-agent/technical-spec.md` (3.2~3.6)
