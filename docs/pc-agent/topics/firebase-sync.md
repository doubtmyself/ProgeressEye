# PC Firebase 동기화

## 목적
PC가 Firebase로 데이터를 읽고/쓰는 경로를 빠르게 찾는다.

## 핵심 코드
- `pc-agent/firebase/realtime_db.py`
- `pc-agent/firebase/device_manager.py`
- `pc-agent/firebase/storage.py`
- `pc-agent/firebase/command_listener.py`
- `pc-agent/main.py`

## Firestore named database 규칙 (필수)

PC 앱은 Firestore REST API를 사용하며, URL에 반드시 `/databases/progress/`를 명시해야 한다.

```python
# ✅ 올바름
f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/progress/documents/users/{uid}"

# ❌ 금지 — default DB를 가리켜 Permission Denied 또는 빈 응답 반환
f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents/users/{uid}"
```

> `device_manager.py`의 모든 Firestore 호출은 URL에 `databases/progress` 포함 확인.

## 데이터 경로
- RTDB: `users/{uid}/devices/{pcId}/tasks/{taskId}`
- 명령: `users/{uid}/commands/*`
- 스크린샷: `users/{uid}/devices/{pcId}/screenshots/latest`
- Firestore: `users/{uid}` / `appConfig/pc` / `appConfig/policies`

## 관련 문서
- API/스키마: `docs/api-spec.md`
- 백엔드 인덱스: `docs/backend/INDEX.md`
