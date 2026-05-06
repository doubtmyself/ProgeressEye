# 모바일 앱 테스트/TDD

## 목적
Android 앱 변경을 할 때 최소 비용으로 회귀를 막고, `domain -> data -> app` 순서로 검증 범위를 넓힌다.

## 기본 원칙
- 새 기능이나 버그 수정은 가능하면 테스트를 먼저 추가한다.
- 가장 먼저 `domain` use case 단위 테스트를 만든다.
- `data`는 순수 변환 로직과 유틸부터 테스트한다.
- `app`은 ViewModel 상태 전이처럼 Android 프레임워크 의존이 낮은 부분부터 테스트한다.
- Compose UI와 Firebase 연동은 마지막 단계에서 다룬다.

## 이 프로젝트의 권장 순서
1. `domain` use case에 fake repository 기반 unit test를 만든다.
2. `data` 유틸/mapper 테스트를 만든다.
3. ViewModel에 테스트 가능한 순수 상태 전이 로직이 있으면 unit test를 추가한다.
4. UI 상호작용이 중요할 때만 `androidTest`나 Compose UI test를 추가한다.

## 현재 기준점
- `mobile-app/domain/src/test/java/com/chg/progeresseye/domain/usecase/CheckExistingSessionUseCaseTest.kt`
- `mobile-app/domain/src/test/java/com/chg/progeresseye/domain/usecase/SendScreenshotCommandUseCaseTest.kt`
- `mobile-app/domain/src/test/java/com/chg/progeresseye/domain/usecase/RecordSubscriptionPurchaseUseCaseTest.kt`
- `mobile-app/data/src/test/java/com/chg/progeresseye/data/util/CommandBuilderTest.kt`

## TDD 루프
1. 실패하는 테스트를 먼저 작성한다.
2. 테스트를 통과시키는 최소 구현만 넣는다.
3. 리팩터링 후 테스트를 다시 돌린다.

## 실행 명령
- 전체 unit test: `./gradlew :app:testDebugUnitTest :data:testDebugUnitTest :domain:test`
- domain만: `./gradlew :domain:test`
- data만: `./gradlew :data:testDebugUnitTest`

## 적용 기준
- 비즈니스 규칙이 바뀌면 `domain` 테스트를 먼저 추가한다.
- Firebase 경로, command payload, 문자열 조합이 바뀌면 `data` 테스트를 먼저 추가한다.
- 화면 문구보다 상태 전이가 중요하면 ViewModel 테스트를 우선한다.
