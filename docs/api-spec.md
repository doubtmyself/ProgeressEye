# Firebase 데이터 구조 및 API 설계서

---

## 1. 개요

ProgressEye는 **Google 로그인 기반 인증**과 Firebase Realtime Database를 중심으로 PC Agent와 Mobile App 간 데이터를 동기화한다. 이미지는 전혀 전송하지 않으며, **막대 픽셀 분석으로 산출된 진행률 숫자만** 저장한다.

**핵심 원칙**: 모든 데이터는 `users/{uid}` 아래에 귀속되어, 같은 Google 계정으로 로그인한 기기만 접근 가능하다.

---

## 2. Realtime Database 스키마

### 2.1 전체 구조

```
progresseye-db/
└── users/
    └── {uid}/                          # Google 계정별 데이터 격리
        ├── profile/                    # 사용자 프로필
        ├── devices/                    # 등록된 PC 목록
        │   └── {pcId}/
        ├── tasks/                      # 작업 진행률 (핵심)
        │   └── {pcId}/
        │       └── {taskId}/
        ├── commands/                   # 원격 명령 큐
        │   └── {pcId}/
        └── settings/                   # 알림 및 앱 설정
            ├── fcmTokens/
            └── notifications/
```

---

### 2.2 profile (사용자 프로필)

```json
{
  "users": {
    "{uid}": {
      "profile": {
        "email": "user@gmail.com",
        "displayName": "홍길동",
        "photoURL": "https://lh3.googleusercontent.com/...",
        "createdAt": 1700000000000,
        "lastLoginAt": 1700100000000
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| email | string | Google 계정 이메일 |
| displayName | string | Google 프로필 이름 |
| photoURL | string | Google 프로필 사진 URL |
| createdAt | number | 최초 가입 시각 (Unix ms) |
| lastLoginAt | number | 마지막 로그인 시각 |

**쓰기**: PC Agent 또는 Mobile App (최초 로그인 시)

---

### 2.3 devices (PC 기기 정보)

PC Agent에서 Google 로그인하면 자동 등록.

```json
{
  "users": {
    "{uid}": {
      "devices": {
        "pc_a1b2c3d4": {
          "name": "작업용 PC",
          "platform": "Windows 11",
          "status": "online",
          "lastSeen": 1700000000000,
          "appVersion": "1.0.0",
          "createdAt": 1700000000000
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
| status | string | "online" / "offline" |
| lastSeen | number | 마지막 통신 시각 (Unix ms) |
| appVersion | string | PC Agent 버전 |
| createdAt | number | 최초 등록 시각 |

> `status`는 Firebase Presence 기능으로 자동 관리.

---

### 2.4 tasks (작업 진행률) — 핵심 데이터

PC에서 모니터링 중인 작업의 실시간 진행률. **막대 픽셀 분석으로 산출된 값.**

```json
{
  "users": {
    "{uid}": {
      "tasks": {
        "pc_a1b2c3d4": {
          "task_001": {
            "label": "프리미어 렌더링",
            "progress": 73.2,
            "status": "running",
            "startedAt": 1700000000000,
            "updatedAt": 1700001000000,
            "estimatedEndAt": 1700003535000,
            "captureIntervalSec": 30
          }
        }
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| label | string | 작업 이름 (사용자 지정) |
| progress | number | 진행률 (0.0~100.0, 소수점 1자리) |
| status | string | "running" / "freeze" / "complete" / "error" / "paused" |
| startedAt | number | 작업 모니터링 시작 시각 |
| updatedAt | number | 마지막 업데이트 시각 |
| estimatedEndAt | number | 예상 완료 시각 (진행 속도 기반 계산) |
| captureIntervalSec | number | 캡처 주기 (초) |

> **이전 대비 삭제**: `progressRaw`, `timeRemaining`, `timeRemainingRaw`, `ocrConfidence` — OCR 관련 필드 전부 제거. 막대 분석은 순수 숫자만 산출.

**쓰기**: PC Agent (Firebase REST API, `requests` 라이브러리 직접 호출)
**읽기**: Mobile App, Cloud Functions

---

### 2.5 commands (원격 명령 큐)

```json
{
  "users": {
    "{uid}": {
      "commands": {
        "pc_a1b2c3d4": {
          "type": "shutdown",
          "requestedAt": 1700001000000,
          "status": "pending",
          "executedAt": null,
          "result": null
        }
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| type | string | "shutdown" / "sleep" |
| requestedAt | number | 요청 시각 |
| status | string | "pending" / "confirmed" / "executed" / "rejected" |
| executedAt | number? | 실행 시각 |
| result | string? | "success" / "failed" + 사유 |

---

### 2.6 settings (알림 및 앱 설정)

```json
{
  "users": {
    "{uid}": {
      "settings": {
        "fcmTokens": {
          "mob_device_1": "dK8x...token_1...",
          "mob_device_2": "eL9y...token_2..."
        },
        "notifications": {
          "complete": true,
          "freeze": true,
          "offline": false
        }
      }
    }
  }
}
```

---

## 3. Cloud Functions

### 3.1 onTaskComplete — 완료 알림 발송

```
트리거: users/{uid}/tasks/{pcId}/{taskId}/status 가 "complete"로 변경 시
동작:
  1. users/{uid}/settings/notifications/complete 확인
  2. true이면 users/{uid}/settings/fcmTokens 의 모든 토큰에 FCM 발송
```

### 3.2 onTaskFreeze — 멈춤 알림 발송

```
트리거: users/{uid}/tasks/{pcId}/{taskId}/status 가 "freeze"로 변경 시
동작:
  1. users/{uid}/settings/notifications/freeze 확인
  2. true이면 FCM 발송
```

### 3.3 onDeviceOffline — 오프라인 알림

```
트리거: users/{uid}/devices/{pcId}/status 가 "offline"으로 변경 시
동작:
  1. 마지막 온라인 시간 확인 (2분 유예)
  2. users/{uid}/settings/notifications/offline 확인
  3. true이면 FCM 발송
```

### 3.4 onUserCreate — 신규 사용자 초기화

```
트리거: Firebase Auth에 새 사용자 생성 시
동작:
  1. users/{uid}/profile 에 이메일, 이름, 사진 URL 저장
  2. users/{uid}/settings/notifications 기본값 설정
```

---

## 4. FCM 메시지 포맷

### 완료 알림

```json
{
  "notification": {
    "title": "작업 완료!",
    "body": "프리미어 렌더링 — 작업용 PC"
  },
  "data": {
    "type": "complete",
    "pcId": "pc_a1b2c3d4",
    "taskId": "task_001",
    "label": "프리미어 렌더링"
  }
}
```

### 멈춤 알림

```json
{
  "notification": {
    "title": "진행 멈춤 감지",
    "body": "프리미어 렌더링 — 5분째 73%에서 멈춤"
  },
  "data": {
    "type": "freeze",
    "pcId": "pc_a1b2c3d4",
    "taskId": "task_001",
    "progress": "73.2",
    "frozenMinutes": "5"
  }
}
```

---

## 5. 보안 규칙 (Database Rules)

```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "auth != null && auth.uid == $uid",
        ".write": "auth != null && auth.uid == $uid",
        
        "profile": {
          ".validate": "newData.hasChildren(['email', 'displayName'])"
        },
        "devices": {
          "$pcId": {
            ".validate": "newData.hasChildren(['name', 'status'])"
          }
        },
        "tasks": {
          "$pcId": {
            "$taskId": {
              ".validate": "newData.hasChildren(['label', 'progress', 'status'])"
            }
          }
        },
        "commands": {
          "$pcId": {
            ".validate": "newData.hasChildren(['type', 'status'])"
          }
        }
      }
    }
  }
}
```

---

## 6. ID 생성 규칙

| ID | 형식 | 생성 주체 | 예시 |
|----|------|-----------|------|
| uid | Firebase Auth 자동 생성 | Google Sign-In | `Uf7xKp2mR...` |
| pcId | `pc_` + 8자리 랜덤 hex | PC Agent (최초 로그인 시) | `pc_a1b2c3d4` |
| taskId | `task_` + 3자리 순번 | PC Agent (영역 추가 시) | `task_001` |
| fcmToken key | 기기 식별자 | Mobile App (로그인 시) | `mob_device_1` |
