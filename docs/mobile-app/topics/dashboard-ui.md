# 모바일 대시보드/UI

## 목적
대시보드 카드, 상태 표시, 주요 UI 컴포넌트를 빠르게 찾는다.

## 핵심 코드
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/dashboard/*`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/settings/SettingsScreen.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/login/LoginScreen.kt`

## 동작 메모
- RTDB 리스너가 `PERMISSION_DENIED`로 취소되면 대시보드에서 세션 정리 로그아웃 플래그를 올리고, 메인 화면에서 즉시 로그아웃 흐름으로 전환한다.

## 관련 문서
- UI 설계: `docs/mobile-app/ui-design.md`
- 요구사항: `docs/mobile-app/requirements.md`
