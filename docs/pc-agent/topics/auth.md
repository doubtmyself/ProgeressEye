# PC 인증/세션

## 목적
PC 앱의 로그인, 자동 로그인, 토큰 갱신, 로그아웃/탈퇴 연관 흐름을 빠르게 찾는다.

## 핵심 코드
- `pc-agent/main.py`
- `pc-agent/auth/google_oauth.py`
- `pc-agent/auth/firebase_auth.py`
- `pc-agent/auth/token_manager.py`

## 확인 포인트
- 로그인 시작: `_do_login()`
- 자동 로그인: `_try_auto_login()`
- 토큰 갱신: `refresh_token()`
- 로그아웃: `_do_logout()`
- 탈퇴 유예 로그인 안내 다이얼로그: `_handle_withdrawal_gate()` (전면 포커스 표시)
- 탈퇴 유예 안내에서 "계속 탈퇴 유지" 선택 시 로그인 에러 재시도 창 없이 앱을 조용히 종료
- 디버그(`-d`) 전용 설정 버튼으로 "탈퇴+7일 시나리오"를 강제 적용: `_on_test_withdrawal_expired()`

## 관련 문서
- 요구사항: `docs/pc-agent/requirements.md`
- 기술설계: `docs/pc-agent/technical-spec.md`
- 정책: `docs/backend/topics/account-policy.md`
