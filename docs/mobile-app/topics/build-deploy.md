# 모바일 빌드/배포

## 목적
Android 빌드, Play 배포 경로를 빠르게 찾는다.

## 핵심 파일
- `mobile-app/app/build.gradle.kts`
- `mobile-app/app/version.properties`
- `mobile-app/gradlew.bat`

## 주요 명령
- 디버그 빌드: `./gradlew :app:assembleDebug`
- Kotlin 컴파일: `./gradlew :app:compileDebugKotlin`
- 배포: `./gradlew publishBundle`

## 비공개 테스트 자동 출시 (publishBundle)
- `mobile-app/app/build.gradle.kts`의 `play` 설정이 기본 `internal` 트랙으로 고정되어 있다.
- `./gradlew publishBundle` 실행 시 내부 테스트 트랙으로 자동 업로드/출시된다.
- 전제 조건
  - `mobile-app/app/google-play-api-key.json` 존재
  - `mobile-app/keystore.properties` 및 서명 키 설정 완료

## 관련 문서
- 프로젝트 개요: `docs/overview.md`
- 기술설계: `docs/mobile-app/technical-spec.md` (빌드/배포)

## 릴리즈 Google 로그인 트러블슈팅
- 증상: 계정 선택 후 로그인 콜백이 오지 않거나 바로 취소되는 것처럼 보임
- 1차 점검: `mobile-app`에서 `./gradlew.bat :app:signingReport` 실행 후 `release` SHA-1/SHA-256 확인
- Firebase 콘솔 점검:
  - Android 앱(`com.chg.progeresseye`)에 릴리즈 인증서 SHA-1/SHA-256 등록
  - Play 배포 앱은 Play App Signing SHA-1/SHA-256도 함께 등록
- 적용: Firebase에서 `google-services.json` 재다운로드 후 `mobile-app/app/google-services.json` 교체
- 참고: 난독화(R8) 자체보다 릴리즈 서명 지문 불일치로 동일 증상이 자주 발생함
