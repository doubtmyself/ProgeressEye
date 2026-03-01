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

## 관련 문서
- 프로젝트 개요: `docs/overview.md`
- 기술설계: `docs/mobile-app/technical-spec.md` (빌드/배포)
