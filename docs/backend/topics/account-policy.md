# 계정/탈퇴 정책

## 정책 요약
- 탈퇴 요청 후 7일 유예
- 유예 만료 후 데이터 삭제
- 요청일 기준 30일 재가입 제한
- 유예기간 중 로그인 시 탈퇴 취소 가능(PC/모바일)

## 정책 기준 문서
- `docs/privacy-policy-ko.md`

## 구현 분담
- 클라이언트(PC/모바일): 안내/확인 UX, 취소 요청
- 서버(Functions): Cloud Tasks 기반 유예 만료 삭제/정리 작업

## 데이터 기준(SoT)
- 탈퇴/재가입 제한 정책의 기준 데이터는 Firestore(`users/{uid}`, `withdrawnUsers/{uid}`)로 단일화한다.
- RTDB는 실시간 상태/명령 전달 전용으로 사용하며, 정책 판정 기준으로 사용하지 않는다.
- Auth UID 재생성(재가입) 우회를 막기 위해 `withdrawnEmails/{emailKey}` 기준도 함께 사용한다.
- 최소 정책 필드 권장값
  - `users/{uid}`: `withdrawalStatus`, `deleteAt`, `rejoinAllowedAt`
  - `withdrawnUsers/{uid}`: `rejoinAllowedAt` (필요 시 `deletedAt` 추가)
  - `withdrawnEmails/{emailKey}`: `rejoinAllowedAt`

## 관련 코드
- PC: `pc-agent/main.py`, `pc-agent/firebase/device_manager.py`
- 모바일: `mobile-app/.../AuthViewModel.kt`, `LoginScreen.kt`, `MainActivity.kt`
- 서버: `functions/index.js`
