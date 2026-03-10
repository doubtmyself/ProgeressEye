# PC Agent 보안 체크리스트

> 마지막 감사: 2026-03-11

---

## 요약

| 항목 | 상태 |
|------|------|
| OAuth 클라이언트 시크릿 하드코딩 | ⚠️ 주의 |
| targetDeviceId 미검증 명령 실행 | ⚠️ 주의 |
| Firebase 토큰을 URL 파라미터로 전송 | ⚠️ 주의 |
| subprocess shell=False | ✅ 안전 |
| 토큰 저장 (Windows keyring) | ✅ 안전 |
| 설정 파일 민감 정보 | ✅ 안전 |
| SSL 검증 | ✅ 안전 |
| 스크린샷 해시 (MD5) | ℹ️ 낮음 |

---

## 1. 인증 / 자격증명

### 1-1. OAuth 클라이언트 시크릿 하드코딩 ⚠️ 주의
- **파일:** `pc-agent/auth/google_oauth.py:30-33`
- **내용:** `CLIENT_SECRET`이 환경변수 fallback으로 소스코드에 하드코딩되어 있음
  ```python
  CLIENT_SECRET = os.environ.get(
      "PROGRESSEYE_OAUTH_CLIENT_SECRET",
      "GOCSPX-...",  # 하드코딩된 시크릿
  )
  ```
- **위험도:** 중간 — 데스크탑(Installed App) OAuth에서 클라이언트 시크릿은 Google 정책상 "공개 정보"로 취급되지만, 소스코드/Git 히스토리 노출은 바람직하지 않음
- **조치:** 환경변수 또는 별도 secrets 파일로 분리, fallback 기본값 제거
- **현재 상태:** 미조치 (기능 우선 개발 단계)

### 1-2. Firebase API Key 하드코딩 ℹ️ 낮음
- **파일:** `pc-agent/auth/firebase_auth.py:20-23`
- **내용:** `FIREBASE_API_KEY`가 환경변수 fallback으로 하드코딩
- **위험도:** 낮음 — Firebase 클라이언트 API 키는 Firebase Rules로 보호되며, Google 공식 문서상 클라이언트 앱에 포함되는 것이 정상
- **조치:** 운영 배포 시 환경변수로 주입 권장
- **현재 상태:** 허용됨

### 1-3. 토큰 저장 ✅ 안전
- **파일:** `pc-agent/auth/token_manager.py`
- **내용:** Firebase ID Token, Refresh Token을 Windows Credential Manager (keyring) 에 저장
- **위험도:** 없음 — OS 보호 영역 사용
- **현재 상태:** 안전

### 1-4. 설정 파일 민감 정보 ✅ 안전
- **파일:** `pc-agent/config.py` (JSON 파일)
- **내용:** uid, device_id, 이메일 등 저장 — 비밀번호/토큰 없음
- **위험도:** 없음
- **현재 상태:** 안전

---

## 2. 명령 처리 (원격 제어)

### 2-1. sleep/shutdown 명령 — targetDeviceId 미제공 시 실행 ⚠️ 주의
- **파일:** `pc-agent/main.py:877-891`
- **내용:** `targetDeviceId`가 null이거나 없으면 필터링 없이 명령 실행
  ```python
  # targetDeviceId가 없으면 → my_device 비교 없이 통과
  if isinstance(target, str) and target and target != my_device:
      continue  # 다른 기기 대상이면 무시
  # target이 None이면 이 블록을 통과 → 명령 실행됨
  ```
- **위험도:** 중간 — Firebase Rules가 자신의 commands 경로에만 쓸 수 있도록 제한하므로 외부 공격자는 불가. 단, 같은 계정의 다른 기기에서 targetDeviceId 없이 쓰면 모든 PC에 명령이 실행됨
- **조치:** sleep/shutdown은 targetDeviceId 필수 검증으로 강화 권장
  ```python
  if cmd_type in ("sleep", "shutdown"):
      if not isinstance(target, str) or target != my_device:
          continue
  ```
- **현재 상태:** 미조치

### 2-2. subprocess 명령 주입 ✅ 안전
- **파일:** `pc-agent/main.py:1093-1115`
- **내용:** sleep/shutdown 명령 실행 시 `shell=False`, 하드코딩된 인자 사용
  ```python
  subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
  subprocess.Popen(["shutdown", "/s", "/t", "30"], shell=False)
  ```
- **위험도:** 없음 — 사용자 입력이 인자로 사용되지 않음
- **현재 상태:** 안전

### 2-3. SSE 명령 중복 처리 방지 ✅ 안전
- **파일:** `pc-agent/main.py:917-971`
- **내용:** `cmdId` + 타임스탬프로 중복/오래된 명령 필터링
- **위험도:** 없음
- **현재 상태:** 안전

---

## 3. 네트워크

### 3-1. Firebase 토큰을 URL 파라미터로 전송 ⚠️ 주의
- **파일:** `pc-agent/firebase/realtime_db.py:70`, `pc-agent/firebase/command_listener.py:93`
- **내용:** Firebase ID Token을 `?auth=<token>` 쿼리 파라미터로 전송
  ```python
  params = {"auth": token}
  ```
- **위험도:** 낮음~중간 — 토큰이 서버 접근 로그, 프록시 로그에 기록될 수 있음. Firebase 권장 방식은 `Authorization: Bearer` 헤더
- **조치:** `headers={"Authorization": f"Bearer {token}"}` 방식으로 변경 권장
- **현재 상태:** 미조치 (Firebase REST API가 두 방식 모두 지원하므로 기능상 문제 없음)

### 3-2. SSL 검증 ✅ 안전
- **파일:** `pc-agent/firebase/realtime_db.py`, `pc-agent/firebase/command_listener.py`
- **내용:** requests 라이브러리 기본값 사용 (SSL 검증 활성화)
- **위험도:** 없음
- **현재 상태:** 안전

---

## 4. 데이터 처리

### 4-1. 스크린샷 해시 MD5 ℹ️ 낮음
- **파일:** `pc-agent/main.py` (스크린샷 캐시 로직)
- **내용:** 스크린샷 중복 업로드 방지를 위한 캐시 키로 MD5 사용
- **위험도:** 없음 — 보안용이 아닌 캐싱용 해시
- **조치:** SHA-256으로 교체 가능 (선택사항)
- **현재 상태:** 기능상 문제 없음

---

## 조치 우선순위

| 우선순위 | 항목 | 난이도 |
|---------|------|--------|
| 높음 | 2-1. sleep/shutdown targetDeviceId 필수 검증 | 낮음 (5분) |
| 중간 | 1-1. OAuth 시크릿 하드코딩 제거 | 중간 |
| 낮음 | 3-1. 토큰 Authorization 헤더로 전환 | 중간 |
| 선택 | 4-1. MD5 → SHA-256 | 낮음 |
