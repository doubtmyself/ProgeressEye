# 데이터 스키마 (RTDB/Firestore)

## 목적
사용자/기기/작업/명령/알림 데이터 경로를 빠르게 확인한다.

## Firestore named database 규칙 (필수)

이 프로젝트는 기본(default) Firestore DB가 아닌 **`"progress"`** named database를 사용한다.

| 플랫폼 | 올바른 접근 방법 |
|---|---|
| 모바일 (Android) | `FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)` |
| PC (Python) | REST URL에 `/databases/progress/` 명시 |

**모바일 주의:** `FirebaseFirestore.getInstance()` (인자 없음)는 기본 DB를 가리키므로 사용 금지.
기본 DB에 대한 쓰기는 Security Rules 거부 또는 무한 대기(hang)를 유발한다.

**PC 주의:** REST URL 예시: `https://firestore.googleapis.com/v1/projects/{project_id}/databases/progress/documents/...`

## 기준 문서
- `docs/api-spec.md`

## 핵심 경로
- RTDB: `users/{uid}/devices/{pcId}/tasks/{taskId}`
- RTDB 명령: `users/{uid}/commands/*`
- RTDB 알림: `users/{uid}/alerts/{alertId}`
- Firestore 플랜: `users/{uid}.plan`
- Firestore 광고 정책(관리자 전용): `appConfig/policies.adFreeModeGlobal`
- Firestore 탈퇴 정책(기준): `users/{uid}.withdrawalStatus`, `deleteAt`, `rejoinAllowedAt`
- Firestore 탈퇴 tombstone(최소): `withdrawnUsers/{uid}.rejoinAllowedAt` (`deletedAt`은 운영 추적용 선택)
- Firestore 이메일 기준 재가입 제한: `withdrawnEmails/{emailKey}.rejoinAllowedAt`
- Firestore PC 오류 보고: `errorReports/{version}/reports/{reportId}` — uid, error, traceback, version, os, ts
