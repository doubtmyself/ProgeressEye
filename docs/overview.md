# ProgressEye 개요

## 프로젝트 구성

```
ProgressEye/
├── pc-agent/        # Windows 데스크톱 에이전트 (Python, PyQt6)
├── mobile-app/      # Android 앱 (Kotlin, Jetpack Compose)
├── functions/       # Firebase Cloud Functions (Node.js)
├── docs/            # 공식 문서(단일 소스)
├── database.rules.json
├── firestore.rules
└── firebase.json
```

## 개발 환경

| 도구 | 권장 버전 | 용도 |
|---|---|---|
| Python | 3.11+ | PC 앱 |
| Android Studio | 최신 | 모바일 앱 |
| Node.js | 20+ | Functions |
| Firebase CLI | 15+ | Firebase 배포 |

## 문서 사용 규칙

- 문서는 `docs/`만 공식 기준으로 관리한다.
- 작업 시작 시 `docs/INDEX.md`를 먼저 확인한다.
