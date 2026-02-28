# Firebase 데이터 구조 및 API 설계서

---

## 1. 개요

ProgressEye는 **Google 로그인 기반 인증**과 Firebase Realtime Database와 Firestore를 중심으로 PC Agent와 Mobile App 간 데이터를 동기화한다. 이미지는 전혀 전송하지 않으며 (스크린샷 요청 제외), **막대 픽셀 분석 또는 OCR로 산출된 진행률 숫자만** 저장한다.

**핵심 원칙**: 모든 데이터는 `users/{uid}` 아래에 귀속되어, 같은 Google 계정으로 로그인한 기기만 접근 가능하다.

---

## 2. Realtime Database 스키마

### 2.1 전체 구조

```
progresseye-db/                          # Realtime Database
└── users/
    └── {uid}/                           # Google 계정별 데이터 격리
        ├── profile/                     # 사용자 프로필
        ├── activeDevice                 # 현재 활성 PC 기기 ID
        ├── mobileSession/               # 모바일 세션 관리
        ├── mobileHeartbeat              # 모바일 하트비트
        ├── deviceStatus/                # 기기별 상태
        │   └── {deviceId}
        ├── heartbeat/                   # 기기별 하트비트
        │   └── {deviceId}
        ├── commands/                    # 원격 명령 (기기별이 아닌 flat 구조)
        │   ├── screenshot
        │   ├── monitor
        │   └── forceLogout
        ├── devices/                     # PC 기기 정보
        │   └── {pcId}/
        │       ├── stats/               # CPU/GPU/RAM
        │       ├── screenshots/latest   # 최신 스크린샷 URL
        │       └── tasks/               # 작업 진행률
        │           └── {taskId}/
        ├── alerts/                      # 알림 기록 (Cloud Function 트리거)
        │   └── {alertId}/
        └── fcmTokens/                   # FCM 토큰 목록
            └── {tokenId}/

progresseye-firestore/                   # Firestore
├── appConfig/
│   └── pc                               # { minVersion: "1.0.0" }
└── users/
    └── {uid}                            # { plan: "free" | "pro" }
```

---

### 2.2 profile (사용자 프로필)

```json
{
  "profile": {
    "email": "user@gmail.com",
    "displayName": "홍길동",
    "lastLoginAt": 1700100000000
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| email | string | Google 계정 이메일 |
| displayName | string | Google 프로필 이름 |
| lastLoginAt | number | 마지막 로그인 시각 (Unix ms) |

**쓰기**: PC Agent 또는 Mobile App (최초 로그인 시)

---

### 2.3 devices (PC 기기 정보)

PC Agent에서 Google 로그인하면 자동 등록.

```json
{
  "devices": {
    "pc_a1b2c3d4": {
      "name": "작업용 PC",
      "platform": "Windows 11",
      "appVersion": "1.0.0",
      "createdAt": 1700000000000,
      "stats": {
        "cpu": 45,
        "gpu": 30,
        "ram": 62
      },
      "screenshots": {
        "latest": { "url": "https://...", "ts": 1700000000 }
      },
      "tasks": {
        "region_1": {
          "p": 73.2,
          "s": "r",
          "l": "프리미어 렌더링"
        }
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| name | string | PC 표시 이름 (기본값: 컴퓨터 이름) |
| platform | string | OS 정보 |
| appVersion | string | PC Agent 버전 |
| createdAt | number | 최초 등록 시각 (Unix ms) |
| stats | object | CPU/GPU/RAM 사용률 (%) |
| screenshots/latest | object | 최신 스크린샷 URL 및 타임스탬프 |
| tasks | object | 작업 진행률 (2.4 참조) |

---

### 2.4 tasks (작업 진행률) — 핵심 데이터

PC에서 모니터링 중인 작업의 실시간 진행률. `devices/{pcId}/tasks/{taskId}` 하위에 위치한다.

```json
{
  "devices": {
    "pc_a1b2c3d4": {
      "tasks": {
        "region_1": {
          "p": 73.2,
          "s": "r",
          "l": "프리미어 렌더링"
        }
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| p | number | 진행률 (0.0~100.0) |
| s | string | "r" (running) / "f" (frozen) / "c" (completed) / "i" (idle) |
| l | string | 작업 라벨 (사용자 지정) |

> 대역폭 절감을 위해 압축된 키 사용. 변경된 작업만 배치 전송 (동일 데이터 스킵).

**쓰기**: PC Agent (Firebase REST API PATCH)
**읽기**: Mobile App (Firebase SDK ValueEventListener)

---

### 2.5 commands (원격 명령)

모바일에서 PC로 보내는 명령. 기기별이 아닌 flat 구조로, PC Agent가 SSE로 실시간 감시한다.

```json
{
  "commands": {
    "screenshot": { "ts": 1700001000, "cmdId": "cmd_abc123" },
    "monitor": { "action": "start", "ts": 1700001000, "cmdId": "cmd_def456" },
    "forceLogout": { "ts": 1700001000 }
  }
}
```

| 명령 | 필드 | 설명 |
|------|------|------|
| screenshot | ts, cmdId | PC 전체 화면 캡처 → Storage 업로드 → RTDB URL 기록 |
| monitor | action, ts, cmdId | "start" / "stop" — 모니터링 시작/정지 |
| forceLogout | ts | 회원 탈퇴 시 PC Agent 강제 로그아웃 + 앱 종료 |

**쓰기**: Mobile App
**읽기**: PC Agent (SSE 스트리밍)

---

### 2.6 alerts (알림 기록)

PC Agent가 이벤트 감지 시 기록. Cloud Function이 트리거되어 FCM 발송.

```json
{
  "alerts": {
    "alert_abc123": {
      "type": "completion",
      "title": "ProgressEye",
      "body": "프리미어 렌더링 — 100% 완료",
      "deviceId": "pc_a1b2c3d4",
      "ts": 1700001000000
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| type | string | "completion" / "stall" / "image_change" |
| title | string | 알림 제목 |
| body | string | 알림 본문 |
| deviceId | string | 발생 PC ID |
| ts | number | 이벤트 시각 (Unix ms) |

### 2.7 fcmTokens (FCM 토큰)

모바일 앱의 FCM 토큰 저장. Cloud Function이 알림 발송 시 조회.

```json
{
  "fcmTokens": {
    "token_xxx": {
      "token": "dK8x...FCM토큰...",
      "updatedAt": { ".sv": "timestamp" }
    }
  }
}
```

### 2.8 기타 노드

| 노드 | 타입 | 설명 |
|------|------|------|
| activeDevice | string | 현재 활성 PC ID ("pc_xxxx") |
| mobileSession | object | 모바일 세션 { sessionId, deviceId, deviceName, updatedAt } |
| mobileHeartbeat | number | 모바일 하트비트 timestamp |
| deviceStatus/{deviceId} | string | "monitoring" / "online" / "offline" |
| heartbeat/{deviceId} | number | 기기 하트비트 timestamp (ms) |

---

## 2B. Firestore 스키마

### appConfig/pc (공개 읽기)

PC Agent 강제 업데이트 체크용. 인증 없이 읽기 가능.

```json
{
  "minVersion": "1.0.0"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| minVersion | string | PC Agent 최소 허용 버전 (시맨틱 버전) |

### users/{uid} (owner 읽기, 쓰기 불가)

사용자 구독 상태. Firebase Console에서만 수정 가능.

```json
{
  "plan": "free"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| plan | string | "free" / "pro" — 구독 상태 |

### Firestore 보안 규칙

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /appConfig/{doc} {
      allow read: if true;        // 공개 읽기 (버전 체크)
      allow write: if true;       // Console에서 관리
    }
    match /users/{uid} {
      allow read: if request.auth != null && request.auth.uid == uid;
      allow write: if false;      // Console에서만 plan 변경
    }
  }
}
```

---

## 3. Cloud Functions

현재 1개의 Cloud Function만 배포되어 있다.

### 3.1 onAlertCreated — 알림 FCM 발송

```
트리거: users/{uid}/alerts/{alertId} 문서 생성 시 (RTDB onCreate)
동작:
  1. alert 문서에서 type, title, body, deviceId 읽기
  2. users/{uid}/fcmTokens/ 전체 조회
  3. 각 토큰에 FCM 메시지 발송:
     - data: { type, title, body, deviceId, alertId }
     - notification: { title, body }
  4. 잘못된 토큰 자동 삭제 (messaging/invalid-registration-token 등)
```

> 설계서에 있던 onTaskComplete, onTaskFreeze, onDeviceOffline, onUserCreate는 구현되지 않았다.
> PC Agent가 직접 alerts 노드에 이벤트를 기록하고, onAlertCreated가 FCM을 발송하는 단순 구조이다.

---

## 4. FCM 메시지 포맷

### 완료 알림

```json
{
  "notification": {
    "title": "ProgressEye",
    "body": "프리미어 렌더링 — 100% 완료"
  },
  "data": {
    "type": "completion",
    "deviceId": "pc_a1b2c3d4",
    "alertId": "alert_abc123"
  }
}
```

### 멈춤 알림

```json
{
  "notification": {
    "title": "ProgressEye",
    "body": "프리미어 렌더링 — 5분째 73%에서 멈춤"
  },
  "data": {
    "type": "stall",
    "deviceId": "pc_a1b2c3d4",
    "alertId": "alert_def456"
  }
}
```

---

## 5. 보안 규칙

### Realtime Database Rules

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid == $uid",
        ".write": "auth != null && auth.uid == $uid"
      }
    }
  }
}
```

### Firestore Rules

Firestore 보안 규칙은 Section 2B 참조.

---

## 6. ID 생성 규칙

| ID | 형식 | 생성 주체 | 예시 |
|----|------|-----------|------|
| uid | Firebase Auth 자동 생성 | Google Sign-In | `Uf7xKp2mR...` |
| pcId | `pc_` + 8자리 랜덤 hex | PC Agent (최초 로그인 시) | `pc_a1b2c3d4` |
| taskId | `region_` + 순번 | PC Agent (영역 추가 시) | `region_1` |
| fcmToken key | `token_` + 랜덤 문자열 | Mobile App (로그인 시) | `token_xxx` |
