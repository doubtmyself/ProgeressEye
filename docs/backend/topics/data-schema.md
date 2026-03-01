# 데이터 스키마 (RTDB/Firestore)

## 목적
사용자/기기/작업/명령/알림 데이터 경로를 빠르게 확인한다.

## 기준 문서
- `docs/api-spec.md`

## 핵심 경로
- RTDB: `users/{uid}/devices/{pcId}/tasks/{taskId}`
- RTDB 명령: `users/{uid}/commands/*`
- RTDB 알림: `users/{uid}/alerts/{alertId}`
- Firestore 플랜: `users/{uid}.plan`
- Firestore 탈퇴 정책(기준): `users/{uid}.withdrawalStatus`, `withdrawalRequestedAt`, `deleteAt`, `rejoinAllowedAt`
- Firestore 탈퇴 tombstone: `withdrawnUsers/{uid}`
