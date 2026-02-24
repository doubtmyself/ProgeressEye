# Firebase 데이터 구조 및 API 설계서

---

## 1. 개요

ProgressEye는 Firebase Realtime Database를 중심으로 PC Agent와 Mobile App 간 데이터를 동기화한다. 이미지는 전혀 전송하지 않으며, OCR 결과 텍스트만 저장한다.

---

## 2. Realtime Database 스키마

### 2.1 전체 구조

```
progresseye-db/
├── pairs/                          # 페어링 대기 코드
│   └── {pairCode}/
├── devices/                        # 등록된 PC 목록
│   └── {pcId}/
├── links/                          # PC ↔ Mobile 연결 정보
│   └── {pcId}/
│       └── {mobileId}/
├── tasks/                          # 작업 진행률 (핵심)
│   └── {pcId}/
│       └── {taskId}/
├── commands/                       # 원격 명령 큐
│   └── {pcId}/
│       └── {commandId}/
└── history/                        # 완료된 작업 이력
    └── {pcId}/
        └── {taskId}/
```

---

### 2.2 pairs (페어링 코드)

PC Agent가 생성한 일회용 페어링 코드. 5분 후 자동 만료.

```json
{
  "pairs": {
    "847291": {
      "pcId": "pc_a1b2c3d4",
      "pcName": "작업용 PC",
      "createdAt": 1700000000000,
      "expiresAt": 1700000300000,
      "status": "waiting"           // "waiting" | "paired" | "expired"
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| pcId | string | PC Agent 고유 ID |
| pcName | string | PC 이름 (사용자 지정) |
| createdAt | number | 생성 시각 (Unix ms) |
| expiresAt | number | 만료 시각 (Unix ms) |
| status | string | 페어링 상태 |

**쓰기**: PC Agent  
**읽기**: Mobile App  

---

### 2.3 devices (PC 기기 정보)

등록된 PC의 기본 정보 및 온라인 상태.

```json
{
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
```

| 필드 | 타입 | 설명 |
|------|------|------|
| name | string | PC 표시 이름 |
| platform | string | OS 정보 |
| status | string | "online" / "offline" |
| lastSeen | number | 마지막 통신 시각 (Unix ms) |
| appVersion | string | PC Agent 버전 |
| createdAt | number | 최초 등록 시각 |

**쓰기**: PC Agent  
**읽기**: Mobile App  

> `status`는 Firebase Presence 기능으로 자동 관리. PC Agent 연결 끊김 시 자동으로 "offline" 전환.

---

### 2.4 links (PC ↔ Mobile 연결)

페어링 완료된 PC와 모바일 기기 간의 연결 정보.

```json
{
  "links": {
    "pc_a1b2c3d4": {
      "mob_x1y2z3": {
        "pairedAt": 1700000000000,
        "fcmToken": "dK8x...token...",
        "notificationSettings": {
          "complete": true,
          "freeze": true,
          "offline": false
        }
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| pairedAt | number | 페어링 완료 시각 |
| fcmToken | string | 모바일 FCM 토큰 (푸시용) |
| notificationSettings | object | 알림 종류별 on/off |

**쓰기**: Mobile App (페어링 완료 시)  
**읽기**: Cloud Functions (FCM 발송 시)  

---

### 2.5 tasks (작업 진행률) — 핵심 데이터

PC에서 모니터링 중인 작업의 실시간 진행률.

```json
{
  "tasks": {
    "pc_a1b2c3d4": {
      "task_001": {
        "label": "프리미어 렌더링",
        "progress": 73,
        "progressRaw": "73%",
        "timeRemaining": "00:42:15",
        "timeRemainingRaw": "00:42:15 remaining",
        "status": "running",
        "ocrConfidence": 0.97,
        "startedAt": 1700000000000,
        "updatedAt": 1700001000000,
        "estimatedEndAt": 1700003535000,
        "captureIntervalSec": 30
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| label | string | 작업 이름 (사용자 지정) |
| progress | number | 진행률 (0~100) |
| progressRaw | string | OCR 원본 텍스트 |
| timeRemaining | string | 남은 시간 (HH:MM:SS) |
| timeRemainingRaw | string | OCR 원본 시간 텍스트 |
| status | string | "running" / "freeze" / "complete" / "error" / "paused" |
| ocrConfidence | number | OCR 신뢰도 (0.0~1.0) |
| startedAt | number | 작업 모니터링 시작 시각 |
| updatedAt | number | 마지막 업데이트 시각 |
| estimatedEndAt | number | 예상 완료 시각 (계산값) |
| captureIntervalSec | number | 캡처 주기 (초) |

**쓰기**: PC Agent  
**읽기**: Mobile App, Cloud Functions  

---

### 2.6 commands (원격 명령 큐)

모바일에서 PC로 보내는 원격 제어 명령.

```json
{
  "commands": {
    "pc_a1b2c3d4": {
      "cmd_001": {
        "type": "shutdown",
        "requestedBy": "mob_x1y2z3",
        "requestedAt": 1700001000000,
        "status": "pending",
        "executedAt": null,
        "result": null
      }
    }
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| type | string | "shutdown" / "sleep" |
| requestedBy | string | 요청한 모바일 기기 ID |
| requestedAt | number | 요청 시각 |
| status | string | "pending" / "confirmed" / "executed" / "rejected" |
| executedAt | number? | 실행 시각 |
| result | string? | "success" / "failed" + 사유 |

**쓰기**: Mobile App (생성), PC Agent (상태 업데이트)  
**읽기**: PC Agent (명령 수신), Mobile App (결과 확인)  

---

## 3. Cloud Functions

### 3.1 onTaskComplete — 완료 알림 발송

```
트리거: tasks/{pcId}/{taskId}/status 가 "complete"로 변경 시
동작:
  1. links/{pcId} 에서 연결된 모바일 기기 목록 조회
  2. 각 기기의 notificationSettings.complete 확인
  3. true인 기기에 FCM 푸시 발송
  4. history/{pcId}/{taskId} 에 완료 기록 저장
```

### 3.2 onTaskFreeze — 멈춤 알림 발송

```
트리거: tasks/{pcId}/{taskId}/status 가 "freeze"로 변경 시
동작:
  1. links/{pcId} 에서 연결된 모바일 기기 목록 조회
  2. 각 기기의 notificationSettings.freeze 확인
  3. true인 기기에 FCM 푸시 발송
```

### 3.3 onDeviceOffline — 오프라인 알림

```
트리거: devices/{pcId}/status 가 "offline"으로 변경 시
동작:
  1. 마지막 온라인 시간 확인 (짧은 끊김 무시: 30초 유예)
  2. links/{pcId} 에서 연결된 모바일 기기 목록 조회
  3. notificationSettings.offline이 true인 기기에 FCM 발송
```

### 3.4 cleanupExpiredPairs — 만료 코드 정리

```
트리거: 매 10분 스케줄 실행
동작:
  1. pairs/ 에서 expiresAt < now() 인 항목 삭제
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
    "progress": "73",
    "frozenMinutes": "5"
  }
}
```

---

## 5. 보안 규칙 (Database Rules)

```json
{
  "rules": {
    "pairs": {
      "$code": {
        ".read": true,
        ".write": "auth != null"
      }
    },
    "devices": {
      "$pcId": {
        ".read": "root.child('links').child($pcId).hasChild(auth.uid)",
        ".write": "auth.uid == $pcId"
      }
    },
    "tasks": {
      "$pcId": {
        ".read": "root.child('links').child($pcId).hasChild(auth.uid)",
        ".write": "auth.uid == $pcId"
      }
    },
    "commands": {
      "$pcId": {
        "$cmdId": {
          ".read": "auth.uid == $pcId || data.child('requestedBy').val() == auth.uid",
          ".write": "auth != null"
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
| pcId | `pc_` + 8자리 랜덤 hex | PC Agent (최초 실행 시) | `pc_a1b2c3d4` |
| mobileId | `mob_` + 8자리 랜덤 hex | Mobile App (최초 실행 시) | `mob_x1y2z3w4` |
| taskId | `task_` + 3자리 순번 | PC Agent (영역 추가 시) | `task_001` |
| commandId | `cmd_` + Firebase push key | Mobile App (명령 전송 시) | `cmd_-NxAbCdEf` |
| pairCode | 6자리 숫자 | PC Agent (페어링 시) | `847291` |
