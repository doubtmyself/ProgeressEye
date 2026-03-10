# 모바일 원격명령/스크린샷

## 목적
모바일에서 PC로 보내는 명령과 스크린샷 요청 경로를 찾는다.

## 핵심 코드
- `mobile-app/app/src/main/java/com/chg/progeresseye/auth/AuthViewModel.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/dashboard/*`

## 명령 경로
- `users/{uid}/commands/screenshot`
- `users/{uid}/commands/monitor`
- `users/{uid}/commands/sleep` — PC 절전 모드 전환 요청
- `users/{uid}/commands/shutdown` — PC 종료 요청 (모바일에서 확인 다이얼로그 표시 후 전송)
- `users/{uid}/commands/forceLogout`

## 관련 문서
- API 문서: `docs/api-spec.md` (commands, screenshots)
- 기술설계: `docs/mobile-app/technical-spec.md` (3.4)
