# Mobile App (Android) - 기술 설계서

---

## 1. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Kotlin | Android 공식 권장, null-safety |
| UI | Jetpack Compose | 선언형 UI, 빠른 개발, Google 권장 |
| 디자인 | Material Design 3 | 일관된 UX, Dynamic Color 지원 |
| 아키텍처 | MVVM + Clean Architecture | 테스트 용이, 관심사 분리 |
| DI | Hilt | Android 표준 DI 프레임워크 |
| 네비게이션 | Navigation Compose | 단일 Activity + Compose 네비게이션 |
| Firebase | Firebase Android SDK | Realtime DB, FCM, Auth |
| 로컬 저장 | DataStore (Preferences) | 설정 값 영속화 |
| 비동기 | Kotlin Coroutines + Flow | 실시간 데이터 스트림 처리 |
| 차트 | Vico | Compose 네이티브 차트 라이브러리 |
| 위젯 | Glance | Compose 기반 앱 위젯 |

---

## 2. 모듈 구조

```
mobile-app/
├── app/
│   ├── src/main/
│   │   ├── java/com/progresseye/
│   │   │   ├── ProgressEyeApp.kt          # Application 클래스
│   │   │   ├── MainActivity.kt             # 단일 Activity
│   │   │   │
│   │   │   ├── data/
│   │   │   │   ├── repository/
│   │   │   │   │   ├── TaskRepository.kt       # 작업 데이터 레포지토리
│   │   │   │   │   ├── DeviceRepository.kt     # 기기 관리 레포지토리
│   │   │   │   │   └── SettingsRepository.kt   # 설정 레포지토리
│   │   │   │   ├── remote/
│   │   │   │   │   ├── FirebaseDataSource.kt   # Firebase Realtime DB
│   │   │   │   │   └── FirebaseMessaging.kt    # FCM 서비스
│   │   │   │   ├── local/
│   │   │   │   │   └── PreferencesDataStore.kt # 로컬 설정 저장
│   │   │   │   └── model/
│   │   │   │       ├── Device.kt               # PC 기기 모델
│   │   │   │       ├── Task.kt                 # 작업 모델
│   │   │   │       └── Command.kt              # 원격 명령 모델
│   │   │   │
│   │   │   ├── domain/
│   │   │   │   ├── usecase/
│   │   │   │   │   ├── ObserveTasksUseCase.kt      # 작업 목록 실시간 관찰
│   │   │   │   │   ├── PairDeviceUseCase.kt         # PC 페어링
│   │   │   │   │   ├── SendCommandUseCase.kt        # 원격 명령 전송
│   │   │   │   │   └── GetProgressHistoryUseCase.kt # 진행 이력 조회
│   │   │   │   └── model/
│   │   │   │       └── TaskStatus.kt                # 상태 enum
│   │   │   │
│   │   │   ├── ui/
│   │   │   │   ├── navigation/
│   │   │   │   │   └── NavGraph.kt             # 네비게이션 그래프
│   │   │   │   ├── theme/
│   │   │   │   │   ├── Theme.kt                # MD3 테마
│   │   │   │   │   ├── Color.kt                # 컬러 팔레트
│   │   │   │   │   └── Type.kt                 # 타이포그래피
│   │   │   │   ├── pairing/
│   │   │   │   │   ├── PairingScreen.kt        # 페어링 화면
│   │   │   │   │   └── PairingViewModel.kt
│   │   │   │   ├── dashboard/
│   │   │   │   │   ├── DashboardScreen.kt      # 대시보드 화면
│   │   │   │   │   ├── DashboardViewModel.kt
│   │   │   │   │   └── components/
│   │   │   │   │       ├── DeviceCard.kt       # PC 카드 컴포넌트
│   │   │   │   │       └── ProgressIndicator.kt # 진행률 표시
│   │   │   │   ├── detail/
│   │   │   │   │   ├── TaskDetailScreen.kt     # 작업 상세 화면
│   │   │   │   │   ├── TaskDetailViewModel.kt
│   │   │   │   │   └── components/
│   │   │   │   │       └── ProgressChart.kt    # 진행 추이 차트
│   │   │   │   └── settings/
│   │   │   │       ├── SettingsScreen.kt       # 설정 화면
│   │   │   │       └── SettingsViewModel.kt
│   │   │   │
│   │   │   ├── widget/
│   │   │   │   ├── ProgressWidget.kt           # 홈 위젯 UI
│   │   │   │   └── WidgetUpdateWorker.kt       # 위젯 갱신
│   │   │   │
│   │   │   └── di/
│   │   │       └── AppModule.kt                # Hilt DI 모듈
│   │   │
│   │   └── res/
│   │       ├── values/
│   │       │   ├── strings.xml
│   │       │   └── themes.xml
│   │       └── drawable/
│   │           └── ic_launcher.xml
│   │
│   ├── build.gradle.kts
│   └── proguard-rules.pro
│
├── gradle/
├── build.gradle.kts            # 프로젝트 수준 빌드
├── settings.gradle.kts
└── gradle.properties
```

---

## 3. 핵심 플로우

### 3.1 실시간 진행률 수신

```kotlin
// 의사코드
class TaskRepository @Inject constructor(
    private val firebaseDataSource: FirebaseDataSource
) {
    fun observeTasks(pcId: String): Flow<List<Task>> {
        return firebaseDataSource
            .observeRealtimeDB("tasks/$pcId")
            .map { snapshot -> snapshot.toTaskList() }
            .distinctUntilChanged()
    }
}

// ViewModel
class DashboardViewModel @Inject constructor(
    private val observeTasksUseCase: ObserveTasksUseCase
) : ViewModel() {
    val uiState: StateFlow<DashboardUiState> = 
        observeTasksUseCase()
            .map { tasks -> DashboardUiState.Success(tasks) }
            .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), Loading)
}
```

### 3.2 FCM 푸시 알림 처리

```kotlin
class ProgressEyeMessagingService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        when (message.data["type"]) {
            "complete"  -> showCompletionNotification(message)
            "freeze"    -> showFreezeWarningNotification(message)
            "offline"   -> showOfflineNotification(message)
        }
    }
}
```

### 3.3 원격 명령 전송

```kotlin
class SendCommandUseCase @Inject constructor(
    private val deviceRepository: DeviceRepository
) {
    suspend operator fun invoke(pcId: String, command: Command): Result<Unit> {
        return deviceRepository.sendCommand(
            pcId = pcId,
            command = command  // SHUTDOWN | SLEEP
        )
        // Firebase "commands/{pcId}" 에 기록
        // PC Agent가 리스닝 중 → 수신 후 실행
    }
}
```

---

## 4. UI 컴포넌트 설계

### 대시보드 카드

```
┌──────────────────────────────────┐
│  🖥️  작업용 PC           🟢 온라인  │
│                                    │
│  프리미어 렌더링                    │
│  ████████████████░░░░  73%         │
│  남은 시간: 00:42:15               │
│                                    │
│  [상세보기]          [⏻ PC 제어]   │
└──────────────────────────────────┘
```

### 상태별 색상

| 상태 | 색상 | 의미 |
|------|------|------|
| running | Primary (Blue) | 정상 진행 중 |
| freeze | Warning (Amber) | 진행 멈춤 감지 |
| complete | Success (Green) | 작업 완료 |
| error | Error (Red) | 오류 발생 |
| offline | Surface Variant (Gray) | PC 오프라인 |

---

## 5. 빌드 및 배포

### 빌드 설정

```kotlin
// build.gradle.kts (app)
android {
    compileSdk = 35
    defaultConfig {
        applicationId = "com.progresseye"
        minSdk = 26        // Android 8.0
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
    }
    buildFeatures {
        compose = true
    }
}
```

### CI/CD

```
GitHub Push → GitHub Actions
    ├── Lint + Unit Test
    ├── Build Debug APK
    └── (Release) → Signed AAB → Play Store 업로드
```
