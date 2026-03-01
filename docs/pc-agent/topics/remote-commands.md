# PC 원격 명령

## 목적
모바일에서 오는 명령(screenshot/monitor/forceLogout) 처리 경로를 찾는다.

## 핵심 코드
- `pc-agent/firebase/command_listener.py`
- `pc-agent/main.py`

## 명령 종류
- `screenshot`
- `monitor` (`start`/`stop`)
- `forceLogout`

## 처리 규칙
- `screenshot` 처리 후 `users/{uid}/commands/screenshot`를 삭제해 재처리를 방지한다.
- `forceLogout` 처리 직전에 `users/{uid}/commands/forceLogout`를 삭제해 재로그인 시 초기 스냅샷 재실행을 방지한다.
- SSE 초기 스냅샷(`/`)에서 발견된 `forceLogout`는 즉시 정리 후 무시하고, 새로 수신된 실시간 `forceLogout` 이벤트만 종료 동작으로 처리한다.

## 관련 문서
- 요구사항: `docs/pc-agent/requirements.md` (FR-PC-007)
- API 문서: `docs/api-spec.md` (commands)
