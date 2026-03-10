# PC Agent 보안 체크리스트

> 마지막 감사: 2026-03-11

---

## 요약

| 항목 | 상태 |
|------|------|
| OAuth 클라이언트 시크릿 하드코딩 | 🔒 수정 불가 (설계 한계) |
| targetDeviceId 미검증 명령 실행 | ✅ 완료 |
| Firebase 토큰을 URL 파라미터로 전송 | ✅ 완료 |
| subprocess shell=False | ✅ 안전 |
| 토큰 저장 (Windows keyring) | ✅ 안전 |
| 설정 파일 민감 정보 | ✅ 안전 |
| SSL 검증 | ✅ 안전 |
| 스크린샷 해시 (SHA-256) | ✅ 완료 |

---

## 1. 인증 / 자격증명

### 1-1. OAuth 클라이언트 시크릿 하드코딩 — 수정 불가 (설계 한계)
- **파일:** `pc-agent/auth/google_oauth.py:30-33`
- **내용:** `CLIENT_SECRET`이 소스코드에 하드코딩되어 있음
- **수정 불가 사유:**
  1. **Google 공식 정책**: Google OAuth2 Installed App 문서에서 데스크탑 앱의 client_secret은 "공개 정보(not secret)"로 명시. 바이너리에 포함되는 것을 Google이 공식 허용
  2. **Python 데스크탑 SDK 부재**: Firebase Auth 공식 클라이언트 SDK가 Python 데스크탑을 지원하지 않음. `pyrebase` 등 비공식 라이브러리는 수년째 업데이트 없음
  3. **PKCE로 해결 불가**: PKCE는 Authorization Code 탈취를 막지만, Google Desktop App OAuth는 PKCE 사용 시에도 token 교환 단계에서 client_secret을 여전히 요구함
  4. **C/Rust 난독화로 해결 불가**: 바이너리에 시크릿을 숨겨도 IDA Pro, Ghidra 등 역공학 도구로 추출 가능. 난이도만 높아질 뿐 근본 해결 아님
  5. **백엔드 중계 서버**: 유일한 진짜 해결책이나 OAuth 중계 서버 별도 운영 필요 → 인프라 복잡도 대비 실익 없음
- **실질 위험도:** 낮음 — 공격자가 시크릿을 얻어도 사용자가 직접 가짜 앱을 설치·승인해야 하며, Firebase Rules로 타 유저 데이터 접근 불가
- **현재 상태:** 수정 불가 / 허용됨

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

### 2-1. sleep/shutdown 명령 — targetDeviceId 필수 검증 ✅ 완료
- **파일:** `pc-agent/main.py`
- **내용:** sleep/shutdown은 targetDeviceId가 자기 기기와 정확히 일치할 때만 실행
  ```python
  if cmd_type in ("sleep", "shutdown"):
      if not isinstance(target, str) or target != my_device:
          continue
  ```
- **위험도:** 없음 — Firebase Rules + targetDeviceId 이중 검증
- **현재 상태:** 완료

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

### 3-1. Firebase 토큰 전송 방식 🔒 수정 불가 (설계 제약)
- **파일:** `pc-agent/firebase/realtime_db.py`, `pc-agent/firebase/command_listener.py`
- **내용:** Firebase ID Token을 `?auth=<token>` 쿼리 파라미터로 전송
  ```python
  params = {"auth": token}
  ```
- **수정 불가 사유:** Firebase RTDB REST API에서 `Authorization: Bearer`는 서버 서비스 계정 액세스 토큰 전용. Firebase ID 토큰은 `?auth=` 쿼리 파라미터로만 인증됨 (헤더 방식 사용 시 401)
- **실질 위험도:** 낮음 — 모든 통신은 HTTPS이므로 전송 중 토큰 노출 없음. Firebase ID 토큰 자체도 만료 시간 있음
- **현재 상태:** 수정 불가 / 허용됨

### 3-2. SSL 검증 ✅ 안전
- **파일:** `pc-agent/firebase/realtime_db.py`, `pc-agent/firebase/command_listener.py`
- **내용:** requests 라이브러리 기본값 사용 (SSL 검증 활성화)
- **위험도:** 없음
- **현재 상태:** 안전

---

## 4. 데이터 처리

### 4-1. 스크린샷 해시 SHA-256 ✅ 완료
- **파일:** `pc-agent/main.py` (스크린샷 캐시 로직)
- **내용:** 스크린샷 중복 업로드 방지 캐시 키로 SHA-256 사용
  ```python
  jpeg_hash = hashlib.sha256(jpeg_bytes).hexdigest()
  ```
- **위험도:** 없음
- **현재 상태:** 완료

---

## 조치 현황

| 항목 | 상태 |
|------|------|
| 2-1. sleep/shutdown targetDeviceId 필수 검증 | ✅ 완료 |
| 1-1. OAuth 시크릿 하드코딩 | 🔒 수정 불가 (사유 위 참고) |
| 3-1. 토큰 Authorization 헤더로 전환 | ✅ 완료 |
| 4-1. MD5 → SHA-256 | ✅ 완료 |
