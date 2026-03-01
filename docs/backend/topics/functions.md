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
- `cleanupWithdrawnUsers`
  - 스케줄 배치(5분 주기)
  - 실행당 배치 제한(`users` 200건, `withdrawnUsers` 500건)
  - 제한된 동시성 처리(기본 10)
  - 단일 인스턴스 실행(`maxInstances: 1`)로 중복 처리 완화
  - 탈퇴 유예 만료 데이터 삭제
  - 재가입 제한 tombstone 정리

## 배포/운영
- 배포: `firebase deploy --only functions`
- 목록 확인: `firebase functions:list`
- 로그 확인: `firebase functions:log`
