# 모바일 세션 관리 (Mobile Session Management)

> 최종 업데이트: 2026-03-19
> 관련 커밋: `f03db42`

---

## 개요

ProgressEye는 계정당 모바일 기기 1대만 동시 로그인을 허용한다.
Firebase Realtime Database의 `users/{uid}/mobileSession` 노드를 통해 세션을 관리한다.

---

## 세션 데이터 구조 (Realtime DB)

```
users/{uid}/mobileSession/
  ├─ sessionId   : String  (UUID, 기기당 고유)
  ├─ deviceId    : String  (앱 설치 시 생성, 재설치 시 변경)
  ├─ deviceName  : String  (제조사 + 모델명)
  └─ updatedAt   : Timestamp
```

---

## 로그인 흐름

```
signInWithGoogle()
  └─ proceedSessionCheck()
        ├─ existingDeviceId == null (신규) → activateMobileSession() → 로그인 완료
        ├─ existingDeviceId == myDeviceId (동일 기기) → activateMobileSession() → 완료
        └─ existingDeviceId != myDeviceId (다른 기기) →
              MobileSessionManager.clearSession()  ← 세션 미확인 표시
              requiresSessionTakeover = true
              pendingUser / pendingUid 저장
```

---

## 세션 탈취 다이얼로그

| 버튼 | 동작 |
|---|---|
| "기존 기기 로그아웃" | `activateMobileSession()` → 새 sessionId 저장 → 로그인 완료 |
| "취소" | `signOut()` + `clearSession()` → 로그인 화면 |

---

## 앱 재시작 시 세션 복원 (`AuthViewModel.init`)

```
Firebase currentUser != null?
  ├─ AND getSessionId() != null → AuthUiState(user=...) → main 화면
  └─ AND getSessionId() == null → signOutFirebaseOnly() + clearSession()
                                   → AuthUiState() → 로그인 화면
```

**sessionId가 null인 경우**:
- 세션 탈취 다이얼로그 중 앱 종료 (정상 종료 없이 프로세스 kill)
- `proceedSessionCheck`에서 conflict 감지 시 즉시 클리어됨

---

## 실시간 세션 감시 (`MainActivity`)

| 리스너 | 감시 대상 | 트리거 조건 |
|---|---|---|
| `startSessionConflictListener` | `mobileSession/sessionId` | remoteSessionId ≠ localSessionId → 강제 로그아웃 |
| `startForceLogoutCommandListener` | `commands/forceLogout` | cmdId 변경 → 강제 로그아웃 |
| `startWithdrawalStatusListener` | Firestore `withdrawalStatus` | `"pending"` → 강제 로그아웃 |

---

## 로컬 저장소 (`mobile_session` SharedPrefs)

| 키 | 설명 |
|---|---|
| `device_id` | 앱 설치 시 생성되는 UUID (`android_...`). 재설치 시 변경 |
| `session_id` | 로그인 성공 후 저장. 탈취 대기 중 또는 로그아웃 시 null |

---

## 관련 클래스

| 클래스 | 역할 |
|---|---|
| `AuthViewModel` | 로그인 상태 관리, 세션 체크/탈취 확인 |
| `GoogleAuthRepository` | Firebase Auth + Credential Manager 래퍼 |
| `MobileSessionManager` | 로컬 sessionId/deviceId SharedPrefs 관리 |
