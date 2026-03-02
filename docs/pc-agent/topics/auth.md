# PC 인증/세션

## 목적
PC 앱의 로그인, 자동 로그인, 토큰 갱신, 로그아웃/탈퇴 연관 흐름을 빠르게 찾는다.

## 핵심 코드
- `pc-agent/main.py`
- `pc-agent/auth/google_oauth.py`
- `pc-agent/auth/firebase_auth.py`
- `pc-agent/auth/token_manager.py`

## 확인 포인트
- 시작 화면 로그인 버튼: `_ensure_login()` 내부 커스텀 로그인 화면에서 버튼 클릭 후 웹 OAuth 시작
- 로그인 실패 메시지는 시작 로그인 화면 내부에 인라인 표시(별도 팝업 재오픈 없음)
- 로그인 시작 화면은 메인 창의 첫 화면으로 동작하고 로그인 성공 후 모니터링 화면으로 전환
- 로그인 시작: `_do_login()`
- 자동 로그인: `_try_auto_login()`
- 토큰 갱신: `refresh_token()`
- 로그아웃: `_do_logout()`
- 탈퇴 유예 로그인 안내 다이얼로그: `_handle_withdrawal_gate()` (전면 포커스 표시)
- 탈퇴 유예 안내에서 "계속 탈퇴 유지" 선택 시 로그인 에러 재시도 창 없이 앱을 조용히 종료
- 탈퇴 요청/취소 정책 쓰기는 Functions HTTPS API(`requestWithdrawal`, `cancelWithdrawal`)로 일원화
- 디버그(`-d`) 전용 설정 버튼으로 "탈퇴+7일 시나리오"를 강제 적용: `_on_test_withdrawal_expired()`
- 디버그(`-d`) 전용 설정 버튼으로 "탈퇴+30일 시나리오"를 강제 적용: `_on_test_rejoin_expired()`
- 재가입 제한 상태(`rejoinAllowedAt > now`)는 로그인 시 날짜 포함 안내 다이얼로그를 표시하고 로그인 차단
- 로그인 에러 다이얼로그에서 Cancel 선택 시 비로그인 모드 진입 없이 앱을 종료

## 관련 문서
- 요구사항: `docs/pc-agent/requirements.md`
- 기술설계: `docs/pc-agent/technical-spec.md`
- 정책: `docs/backend/topics/account-policy.md`
