# 보안 체크리스트

> 마지막 감사: 2026-03-11

## 문서 목록

| 문서 | 대상 |
|------|------|
| [pc-agent.md](./pc-agent.md) | PC 에이전트 (Python) |
| [android.md](./android.md) | Android 앱 (Kotlin) |

---

## 전체 현황

| 심각도 | 항목 | 대상 | 상태 |
|--------|------|------|------|
| ✅ 완료 | sleep/shutdown targetDeviceId 필수 검증 | PC Agent | 완료 |
| 🔒 수정 불가 | OAuth 클라이언트 시크릿 소스코드 노출 | PC Agent | Google 정책상 허용 / Python 데스크탑 SDK 부재 / PKCE·난독화 모두 근본 해결 불가 |
| ✅ 완료 | Firebase 토큰을 URL 파라미터로 전송 | PC Agent | Authorization 헤더로 변경 완료 |
| ✅ 완료 | 스크린샷 URL 화이트리스트 검증 없음 | Android | Firebase Storage 도메인 검증 완료 |
| ✅ 완료 | MD5 → SHA-256 (스크린샷 캐시 해시) | PC Agent | 완료 |
| ✅ 안전 | subprocess shell=False (명령 주입 없음) | PC Agent | 완료 |
| ✅ 안전 | 토큰 Windows Keyring 저장 | PC Agent | 완료 |
| ✅ 안전 | SSL 검증 활성화 | PC Agent | 완료 |
| ✅ 안전 | R8/ProGuard 난독화 | Android | 완료 |
| ✅ 안전 | Timber 릴리즈 로그 비활성화 | Android | 완료 |
| ✅ 안전 | exported 컴포넌트 최소화 | Android | 완료 |
| ✅ 안전 | WebView 미사용 | Android | 완료 |
| ✅ 안전 | Firebase Rules (소유자 전용) | 공통 | 완료 |
