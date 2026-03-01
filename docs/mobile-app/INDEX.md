# 모바일 앱 문서 인덱스

Android 앱 관련 문서를 기능 항목별로 정리한 안내 문서입니다.

## 항목별 목차

## A) 세분화 항목 문서
- 인증/세션: `docs/mobile-app/topics/auth-session.md`
- 대시보드/UI: `docs/mobile-app/topics/dashboard-ui.md`
- 원격명령/스크린샷: `docs/mobile-app/topics/commands-screenshot.md`
- 빌드/배포: `docs/mobile-app/topics/build-deploy.md`

## 1) 개요/구조
- 기능 요구사항: `docs/mobile-app/requirements.md`
- 기술 설계(아키텍처/플로우): `docs/mobile-app/technical-spec.md`
- UI 설계(화면/컴포넌트): `docs/mobile-app/ui-design.md`

## 2) 실행/빌드/배포
- 기본 빌드: `docs/mobile-app/topics/build-deploy.md`
- Play 자동배포(GPP): `docs/mobile-app/topics/build-deploy.md`
- 앱 모듈 설정: `mobile-app/app/build.gradle.kts`

## 3) 화면/상태 흐름
- 로그인/대시보드/설정 화면 요구사항: `docs/mobile-app/requirements.md`
- Compose 화면 구조/네비게이션: `docs/mobile-app/ui-design.md` -> 2, 3장
- 상태관리(ViewModel/UiState): `docs/mobile-app/technical-spec.md` -> 4장

## 4) 실시간 연동/원격 명령
- RTDB 리스너/데이터 최적화: `docs/mobile-app/technical-spec.md` -> 3.2
- 명령 전송(screenshot/monitor/forceLogout): `docs/mobile-app/technical-spec.md` -> 3.4
- 데이터 스키마 상세: `docs/api-spec.md`

## 5) 알림/FCM
- 기능 요구사항: `docs/mobile-app/requirements.md` -> FR-MOB-004
- 채널/알림 UI 설계: `docs/mobile-app/ui-design.md` -> 6장
- Cloud Functions 연계: `docs/backend/INDEX.md` -> Functions

## 6) 계정/탈퇴 정책(최신)
- 모바일 탈퇴 요청(7일 유예, 30일 재가입 제한) + 로그인 시 탈퇴 취소 확인:
  - `mobile-app/app/src/main/java/com/chg/progeresseye/auth/AuthViewModel.kt`
  - `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/login/LoginScreen.kt`
  - `mobile-app/app/src/main/java/com/chg/progeresseye/MainActivity.kt`
- 안내 문구 리소스:
  - `mobile-app/app/src/main/res/values-ko/strings.xml`
  - `mobile-app/app/src/main/res/values/strings.xml`

## 작업별 빠른 링크

| 작업 | 먼저 볼 문서 |
|---|---|
| 로그인 흐름 수정 | `docs/mobile-app/technical-spec.md` 3.1 + `MainActivity.kt` |
| 대시보드 카드/상태 표시 변경 | `docs/mobile-app/ui-design.md` 3.3 |
| 원격 명령 추가 | `docs/mobile-app/technical-spec.md` 3.4 + `docs/api-spec.md` |
| 알림 동작 변경 | `docs/mobile-app/ui-design.md` 6장 + Functions 문서 |
