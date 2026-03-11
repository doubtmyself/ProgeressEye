# 모바일 대시보드/UI

## 목적
대시보드 카드, 상태 표시, 주요 UI 컴포넌트를 빠르게 찾는다.

## 핵심 코드
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/dashboard/*`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/settings/SettingsScreen.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/login/LoginScreen.kt`

## 동작 메모
- RTDB 리스너가 `PERMISSION_DENIED`로 취소되면 대시보드에서 세션 정리 로그아웃 플래그를 올리고, 메인 화면에서 즉시 로그아웃 흐름으로 전환한다.
- 대시보드에는 PC 앱 설치 링크 카드가 항상 표시되고, Microsoft Store 바로가기/링크 공유/링크 복사 액션을 제공한다.
- 기기 미등록 상태 화면과 기기 목록 하단 모두 같은 설치/공유 CTA를 제공한다.
- 아래로 스와이프 새로고침 시 heartbeat 기반 연결 상태를 재검증하고 완료 토스트를 표시한다.
- 대시보드 진입 시 `devices`/`deviceStatus` 초기 1회 스냅샷을 함께 조회해, 등록된 PC가 없어도 로딩이 멈추지 않고 즉시 빈 상태 화면으로 전환한다.
- 설정 > 정보(About) 카드의 "오픈소스 라이선스" 항목을 누르면 라이선스 목록 화면(`OssLicensesActivity`)이 열린다.

## 작업 상태 표시 (Task Status)

PC Agent에서 Firebase `tasks/{taskId}.s` 에 쓰는 상태 코드를 모바일 카드에 반영한다.

| 상태 코드 | 배지 색상 | 진행바 색상 | 카드 부제 |
|-----------|-----------|-------------|-----------|
| `"r"` (running) | 녹색 | 원래 색상 | 진행 중 |
| `"f"` (frozen) | 노란색/주황 | 주황 | 변화 감지되지 않음 |
| `"c"` (completed) | 녹색(완료) | 녹색 | 완료됨 |
| `"s"` (stopped) | 회색 | 회색 | ⚠ 화면 변경으로 모니터링 중지됨 |
| `"i"` (idle) | 회색 | 회색 | 대기 중 |

- 상태별 배지(`StatusBadge`)와 진행바(`GradientProgressBar`) 색상이 각각 독립 처리된다.
- stopped 상태는 `DashboardModels.kt`의 `TaskStatus.STOPPED = "s"` 상수로 관리한다.

## 멀티 PC UI 컴포넌트 (Free 플랜)

- **조건**: `userPlan == "free"` + `!isAdFreeMode` + 등록 PC 2대 이상
- **`DeviceSelectorTabs`**: 가로 스크롤 가능한 칩 목록. 선택된 PC는 파란 테두리+배경, 나머지는 기본 칩 스타일. 선택 인덱스는 `rememberSaveable(mutableIntStateOf(0))`로 유지.
- **`ProUpgradeBanner`**: 다크 카드 형태. "여러 PC를 동시에 보려면 / Pro로 업그레이드하세요" 문구 + "Pro 구독" 버튼 (탭하면 구독 탭으로 이동).
- **Pro/Ad-free 플랜**: 탭/배너 없이 모든 PC 카드 동시 표시.

## 관련 문서
- UI 설계: `docs/mobile-app/ui-design.md`
- 요구사항: `docs/mobile-app/requirements.md`
