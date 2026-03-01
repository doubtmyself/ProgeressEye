# PC Firebase 동기화

## 목적
PC가 Firebase로 데이터를 읽고/쓰는 경로를 빠르게 찾는다.

## 핵심 코드
- `pc-agent/firebase/realtime_db.py`
- `pc-agent/firebase/device_manager.py`
- `pc-agent/firebase/storage.py`
- `pc-agent/firebase/command_listener.py`
- `pc-agent/main.py`

## 데이터 경로
- RTDB: `users/{uid}/devices/{pcId}/tasks/{taskId}`
- 명령: `users/{uid}/commands/*`
- 스크린샷: `users/{uid}/devices/{pcId}/screenshots/latest`
- Firestore: `users/{uid}` / `appConfig/pc`

## 관련 문서
- API/스키마: `docs/api-spec.md`
- 백엔드 인덱스: `docs/backend/INDEX.md`
