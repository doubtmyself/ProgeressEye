# 모바일 인증/세션

## 목적
로그인, 세션 takeover, 탈퇴 유예 로그인 취소 흐름을 찾는다.

## 핵심 코드
- `mobile-app/app/src/main/java/com/chg/progeresseye/auth/AuthViewModel.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/auth/GoogleAuthRepository.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/MainActivity.kt`

## 확인 포인트
- Google 로그인 성공 후 분기
- 세션 takeover 확인 다이얼로그
- 탈퇴 유예기간 로그인 시 탈퇴 취소 다이얼로그
- 로그인 상태에서 Firestore `users/{uid}.withdrawalStatus == pending` 수신 시 자동 로그아웃

## 관련 문서
- 요구사항: `docs/mobile-app/requirements.md`
- 기술설계: `docs/mobile-app/technical-spec.md`
