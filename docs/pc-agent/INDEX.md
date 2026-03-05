# PC 앱 문서 인덱스

PC Agent 관련 문서를 기능 항목별로 정리한 안내 문서입니다.

## 항목별 목차

## A) 세분화 항목 문서
- 인증/세션: `docs/pc-agent/topics/auth.md`
- 모니터링/감지: `docs/pc-agent/topics/monitoring.md`
- Firebase 동기화: `docs/pc-agent/topics/firebase-sync.md`
- 원격 명령: `docs/pc-agent/topics/remote-commands.md`
- 런타임 운영: `docs/pc-agent/topics/runtime-operations.md`
- 빌드/배포: `docs/pc-agent/topics/build-deploy.md`
- 개발용 터미널 축약어: `docs/pc-agent/topics/dev-aliases.md`
- 스토어 등록 문안: `docs/pc-agent/topics/store-listing.md`

## 1) 개요/구조
- 기능 요구사항: `docs/pc-agent/requirements.md`
- 기술 설계(모듈/플로우/설정): `docs/pc-agent/technical-spec.md`
- 실무 실행/배포: `docs/pc-agent/topics/build-deploy.md`

## 2) 실행/빌드/배포
- 로컬 실행/초기설정: `docs/pc-agent/topics/build-deploy.md`
- Tesseract 설치(OCR 모드): `docs/pc-agent/topics/build-deploy.md`
- EXE/MSIX 패키징: `docs/pc-agent/topics/build-deploy.md`
- Microsoft Store 설명/메타 문안: `docs/pc-agent/topics/store-listing.md`

## 3) 감지 파이프라인
- 영역 선택/바 탐지/OCR 모드: `docs/pc-agent/technical-spec.md` -> 핵심 플로우 3.2~3.5
- 모니터링 중 분석 경로(bar_analyzer 중심): `docs/pc-agent/technical-spec.md` -> 3.2b
- 성능/최적화: `docs/pc-agent/topics/monitoring.md`
- 진행률 바 선택 안내(이미지 상단/설명 하단, 4초 샘플 순환): `docs/pc-agent/topics/monitoring.md`
- OCR 퍼센트/최대수치 모드 규칙: `docs/pc-agent/topics/monitoring.md`

## 4) Firebase 연동
- 인증/토큰/자동로그인: `docs/pc-agent/technical-spec.md` -> 3.1
- RTDB/Firestore 연동 개요: `docs/pc-agent/topics/firebase-sync.md`
- 데이터 경로 상세: `docs/api-spec.md`

## 5) 원격 제어/알림
- 명령 수신(SSE): `docs/pc-agent/requirements.md` -> FR-PC-007
- 스크린샷/모니터링 제어/forceLogout: `docs/pc-agent/topics/remote-commands.md`
- 알림 구조/FCM: `docs/api-spec.md` -> alerts / Cloud Functions
- 로컬 Windows 시스템 알림(화면 변경 중지/완료/프리징): `docs/pc-agent/topics/monitoring.md`

## 6) 계정/탈퇴 정책(최신)
- PC 탈퇴 요청(7일 유예, 30일 재가입 제한) 구현 기준:
  - `pc-agent/main.py`
  - `pc-agent/firebase/device_manager.py`
  - `pc-agent/utils/i18n.py`
- 정책 문서: `docs/privacy-policy-ko.md`, `docs/privacy-policy-en.md`

## 7) 문제 해결(추천 읽기 순서)
- 로그인/토큰 문제: `docs/pc-agent/technical-spec.md` -> 3.1, 6
- 영역 감지/오버레이 문제: `docs/pc-agent/technical-spec.md` -> 3.2~3.6
- Firebase 동기화 문제: `docs/api-spec.md` + `docs/pc-agent/topics/firebase-sync.md`

## 작업별 빠른 링크

| 작업 | 먼저 볼 문서 |
|---|---|
| 새 영역 등록 로직 수정 | `docs/pc-agent/technical-spec.md` 3.2, 3.6 |
| 진행률 분석 정확도 개선 | `docs/pc-agent/technical-spec.md` 3.3~3.5 |
| Firebase 경로 변경 | `docs/api-spec.md` + `docs/pc-agent/topics/firebase-sync.md` |
| 로그인/탈퇴 정책 변경 | `docs/privacy-policy-ko.md`, `docs/privacy-policy-en.md` + `pc-agent/main.py` |
