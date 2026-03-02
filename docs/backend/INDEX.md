# 백엔드/Firebase 문서 인덱스

Firebase 데이터 구조, Cloud Functions, 계정 정책 관련 문서 모음입니다.

## A) 세분화 항목 문서
- 데이터 스키마: `docs/backend/topics/data-schema.md`
- Functions: `docs/backend/topics/functions.md`
- 계정/탈퇴 정책: `docs/backend/topics/account-policy.md`
- 배포 가이드: `docs/backend/topics/deploy.md`

## 1) 데이터 구조
- 상세 API/스키마: `docs/api-spec.md`
- 시스템 아키텍처 개요: `docs/architecture.md`

## 2) Cloud Functions
- 구현 파일: `functions/index.js`
- 배포 방법: `docs/backend/topics/deploy.md`
- 현재 핵심 함수
  - `onAlertCreated`: RTDB alerts 트리거 -> FCM 발송
  - `requestWithdrawal`: 탈퇴 정책 쓰기 HTTPS API
  - `cancelWithdrawal`: 탈퇴 취소 정책 쓰기 HTTPS API
  - `onUserWithdrawalChanged`: users 문서 변화 감지 후 탈퇴 정리 Task 예약
  - `onWithdrawnUserChanged`: withdrawnUsers 문서 변화 감지 후 tombstone 정리 Task 예약
  - `processWithdrawalCleanup`: Cloud Tasks로 유예 만료 사용자 정리
  - `processWithdrawnTombstoneCleanup`: Cloud Tasks로 tombstone 만료 정리
  - `backfillWithdrawnTombstoneCleanup`: 10분 주기 누락 tombstone 재수집/Task 예약

## 3) 계정/탈퇴 정책
- 정책 명시: `docs/privacy-policy-ko.md`
- 현재 정책(운영 기준)
  - 탈퇴 요청 후 7일 유예
  - 유예 만료 시 데이터 삭제
  - 요청일 기준 30일 재가입 제한
  - 유예기간 로그인 시 탈퇴 취소 가능(PC/모바일 UX)

## 4) 규칙/환경 설정 파일
- RTDB Rules: `database.rules.json`
- Firestore Rules: `firestore.rules`
- Firebase 프로젝트 설정: `firebase.json`

## 5) 운영 체크리스트

| 점검 항목 | 확인 위치 |
|---|---|
| Functions 배포 상태 | `firebase functions:list` |
| Task Queue 동작 로그 | `firebase functions:log` |
| Firestore users/withdrawnUsers 상태 | Firebase Console Firestore |
| RTDB users/{uid}/withdrawal 상태 | Firebase Console RTDB |
| 개인정보처리방침 반영 상태 | `docs/privacy-policy-ko.md` |
