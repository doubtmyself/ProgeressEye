# Cloud Functions

## 목적
배포된 함수와 역할을 빠르게 확인한다.

## 구현 파일
- `functions/index.js`
- Runtime baseline: Node.js 22 (`functions/package.json` -> `engines.node`)

## 현재 함수
- `onAlertCreated`
  - RTDB alerts 생성 트리거
  - FCM 발송 + stale token 정리
- `onUserWithdrawalChanged`
  - Firestore `users/{uid}` 변경 감지
  - `withdrawalStatus == pending` 전환 시 `processWithdrawalCleanup` 작업 예약
- `onWithdrawnUserChanged`
  - Firestore `withdrawnUsers/{uid}` 변경 감지
  - `rejoinAllowedAt` 기준으로 `processWithdrawnTombstoneCleanup` 작업 예약
- `processWithdrawalCleanup`
  - Cloud Tasks(task queue function) 기반 실행
  - `deleteAt` 도달 시 RTDB/Firestore/Auth 사용자 데이터 정리
  - `withdrawnUsers/{uid}` tombstone 최소 필드(`rejoinAllowedAt`, 선택 `deletedAt`) 생성/갱신
  - `withdrawnEmails/{emailKey}` tombstone 생성/갱신(UID 재생성 우회 방지)
  - `processWithdrawnTombstoneCleanup` 작업 예약
- `processWithdrawnTombstoneCleanup`
  - `rejoinAllowedAt` 도달 시 `withdrawnUsers/{uid}` + `withdrawnEmails/{emailKey}` tombstone 삭제
- `backfillWithdrawnTombstoneCleanup`
  - 10분 주기 스케줄러
  - `rejoinAllowedAt <= now` 인 만료 tombstone을 재수집해 cleanup task 재예약

## 탈퇴 정리 아키텍처
- 기존 5분 배치 스캔 대신, 사용자 단위 지연 Task를 생성한다.
- 최소 저장 필드
  - `users/{uid}`: `withdrawalStatus`, `deleteAt`, `rejoinAllowedAt`
  - `withdrawnUsers/{uid}`: `rejoinAllowedAt` (+ 운영 추적이 필요하면 `deletedAt`)
  - `withdrawnEmails/{emailKey}`: `rejoinAllowedAt`
- 장점
  - 주기적 대량 스캔 쿼리 감소
  - 사용자별 정확한 실행 시점 제어
  - 작업 실패 시 Cloud Tasks 재시도로 복구
- 안전장치
  - 작업은 항상 현재 Firestore 상태(`withdrawalStatus`, `deleteAt`, `rejoinAllowedAt`)를 재검증한다.
  - 중복 예약이 발생해도 조건 미충족이면 no-op 처리한다.
  - 배포 공백/이벤트 누락 대비 백필 스케줄러가 만료 tombstone을 주기적으로 보정한다.

## 배포/운영
- 배포: `firebase deploy --only functions`
- 목록 확인: `firebase functions:list`
- 로그 확인: `firebase functions:log`
