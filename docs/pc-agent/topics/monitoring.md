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

### 병렬 분석
- 영역별 `ThreadPoolExecutor(max_workers=os.cpu_count())` — OCR/이미지 처리는 CPU 바운드이므로 코어 수만큼만 병렬 실행.
- 각 영역마다 스킵 가드: 동일 영역 분석이 이미 실행 중이면 새 요청을 즉시 드롭 (`_capturing_regions: set[str]` + Lock).
- UI 업데이트는 `action_queue.put(fn)` 패턴으로 메인 스레드에서 처리.

### 하트비트 / Stats 동기화
- 하트비트는 60초마다 단일 daemon 스레드로 전송. 이전 스레드가 살아있으면 새 스레드 생성 스킵 (네트워크 지연 시 스레드 누적 방지).
- HW stats(CPU/GPU/RAM)는 **30초** 간격으로 RTDB에 동기화.

### 이미지 유사도 캐싱
- 매 캡처 사이클에서 template 이미지의 64×64 grayscale 배열을 `_template_gray_cache[(region_id, bar_bbox)]`에 캐시.
- 캐시 히트 시 template 쪽 resize/cvtColor 생략 — 현재 캡처(img2)만 신선하게 계산.
- 템플릿 교체(`_save_template`) 또는 삭제(`_delete_template`) 시 캐시 자동 무효화.

### 작업 상태 (Task Status)
- 모니터링 시작 시 모든 영역 상태 → `running` (Firebase `"r"`).
- 진행률 완료 조건 + 지연 확인 충족 → 해당 영역 `completed` (Firebase `"c"`).
- 화면 변경 감지(템플릿 불일치) → 해당 영역 `stopped` (Firebase `"s"`).
- 멈춤 감지(N분 미변화) → 해당 영역 `frozen` (Firebase `"f"`).
- **모든 영역이 `completed` 또는 `stopped` 상태가 되면 모니터링 자동 종료.**
- 카드에 표시: 모니터링 중 체크박스/타입 배지 감춤 → 상태 레이블 표시.

### OCR 미리보기 모드 규칙
- `퍼센트(%)` 모드에서는 기준 수치 입력이 비활성화된다.
- `감지 숫자(max수치)` 모드에서는 `%`가 없는 숫자만 대상으로 탐지한다.
- max 수치를 기준으로 내부 진행률(0~100%)을 계산해 카드/알람/영역 보기와 동일하게 사용한다.

### 완료 알람 규칙
- 바/OCR 모두 카드에서 완료 알람 임계값과 완료 확인 지연(분)을 설정할 수 있다.
- 완료 판정은 표시 단위(소수 1자리) 기준으로 임계값을 비교해 100.0% 표기와 실제 완료 판정이 일치하도록 처리한다.

### 작업 수정(바) 저장 규칙
- `작업 수정` 확인 시 현재 선택 영역 캡처를 템플릿으로 다시 저장해 이후 화면 변경 감지 기준을 최신화한다.
- `작업 수정` 프리뷰는 실시간 화면이 아니라 저장된 템플릿(최초 선택/재선택 기준)을 표시한다.

### 바 영역 재선택 (RegionEditor)
- `BarPreviewDialog`의 [재선택]을 누르면 `RegionEditor` 오버레이가 열린다 (`AreaSelector` 대신 기존 영역을 8핸들로 편집).
- 드래그 후 300ms debounce로 `BarFinder.find()`를 백그라운드 스레드에서 실행.
- 탐지된 바 위치를 선택 영역 안에 빨간 반투명 사각형으로 오버레이 표시.
- 오버레이 열릴 때도 초기 탐지 즉시 실행.

### 로컬 시스템 알림 규칙 (Windows)
- `화면 변경으로 중지`, `작업 완료`, `프리징 감지` 이벤트에서 Windows 시스템 알림을 표시한다.
- RTDB/FCM 모바일 알림과 별개로 동작한다.

### OCR 런타임 백엔드 규칙
- 기본 1순위는 RapidOCR(ONNX Runtime)이다.
- 1순위 초기화 실패 시 PaddleOCR 호환 모드로 자동 전환한다.
- 호환 모드 전환 시 앱 시작 후 안내 다이얼로그를 표시하며, 모니터링 기능은 유지된다.
- 디버그 모드 (`pe-run -d`) 실행 시 OCR 크롭 이미지를 로컬에 저장한다.

### 진행률 바 영역 선택 안내
- 바 영역 선택 시작 시 안내 팝업에서 `게이지가 조금이라도 찬 화면` 기준 캡처를 권장한다.
- 안내 팝업 레이아웃은 `샘플 이미지(위) -> 설명 문구(아래)` 순서로 표시한다.
- 예시 이미지는 `pc-agent/resources/progress-bar-sample.png` + `pc-agent/sampleBar/image*.png`를 불러와 4초 간격으로 순환한다.

## 관련 문서
- 요구사항: `docs/pc-agent/requirements.md` (FR-PC-002~005)
- 기술설계: `docs/pc-agent/technical-spec.md` (3.2~3.6)
