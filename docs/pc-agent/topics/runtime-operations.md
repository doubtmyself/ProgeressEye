# PC 런타임 운영

## 목적
운영 중 자주 확인하는 항목(상태/성능/하드웨어 샘플러/알림 조건)을 빠르게 찾는다.

## 핵심 항목
- 하드웨어 샘플러: CPU/GPU/RAM 수집
- 완료 조건/지연 알림
- 프리징 감지
- 이미지 변경 감지
  - 진행률 바는 내부 채움 영역을 제외하고, 바 외곽선/주변 UI 변화만 비교해 모니터링 중지 여부를 판단
  - OCR 작업도 이미지 변경 감지가 적용되며, OCR 숫자 영역은 비교에서 제외하고 주변 변화로 중지 여부를 판단
  - 외곽선/주변 변화 감지를 위해 이미지 유사도 임계값은 높은 값(민감 감지)으로 적용한다.

## 관련 코드
- `pc-agent/core/system_monitor.py`
- `pc-agent/core/freeze_detector.py`
- `pc-agent/main.py`

## 관련 문서
- 기술설계: `docs/pc-agent/technical-spec.md`
- API/알림 구조: `docs/api-spec.md`
