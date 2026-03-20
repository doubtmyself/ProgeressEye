import com.github.triplet.gradle.androidpublisher.ReleaseStatus
import java.util.Properties
import java.io.FileInputStream
import java.io.FileOutputStream

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.google.services)
    alias(libs.plugins.gradle.play.publisher)
    alias(libs.plugins.firebase.crashlytics.plugin)
    alias(libs.plugins.hilt)
}

// --- 버전 관리 로직 시작 ---
val versionPropsFile = file("version.properties")
val versionProps = Properties()

if (versionPropsFile.exists()) {
    versionProps.load(FileInputStream(versionPropsFile))
} else {
    // 초기값 설정
    versionProps["VERSION_CODE"] = "1"
    versionProps["VERSION_NAME_PREFIX"] = "1.0.0"
    versionProps.store(FileOutputStream(versionPropsFile), null)
}

val vCode = (versionProps["VERSION_CODE"] as String).toInt()
val vNamePrefix = versionProps["VERSION_NAME_PREFIX"] as String
val vName = "$vNamePrefix.$vCode"

tasks.register("incrementVersionCode") {
    onlyIf {
        val publishTask = tasks.findByName("publishBundle")
        val isSuccess = publishTask != null && publishTask.state.failure == null
        if (isSuccess) {
            println("[:incrementVersionCode] publishBundle success detected. Incrementing version...")
        } else {
            println("[:incrementVersionCode] publishBundle failed or skipped.")
        }
        isSuccess
    }
    doLast {
        val currentCode = (versionProps["VERSION_CODE"] as String).toInt()
        val nextCode = currentCode + 1
        versionProps["VERSION_CODE"] = nextCode.toString()
        versionProps.store(FileOutputStream(versionPropsFile), null)
        println("Deploy Successful! Version Code incremented to $nextCode for next release.")
    }
}
// --- 버전 관리 로직 끝 ---

android {
    namespace = "com.chg.progeresseye"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.chg.progeresseye"
        minSdk = 24
        targetSdk = 36
        versionCode = vCode
        versionName = vName

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    signingConfigs {
        create("release") {
            val keystorePropertiesFile = rootProject.file("keystore.properties")
            val keystoreProperties = Properties()
            if (keystorePropertiesFile.exists()) {
                keystoreProperties.load(FileInputStream(keystorePropertiesFile))
            }

            storeFile = file(keystoreProperties["storeFile"] ?: "release.jks")
            storePassword = keystoreProperties["storePassword"] as String? ?: "android"
            keyAlias = keystoreProperties["keyAlias"] as String? ?: "key0"
            keyPassword = keystoreProperties["keyPassword"] as String? ?: "android"
        }
    }

    buildTypes {
        debug {
            isDebuggable = true
            // 디버그 빌드 ABI 분리: arm64-v8a만 설치 → APK 크기 감소 → 설치/시작 속도 향상
            splits.abi {
                isEnable = true
                reset()
                include("arm64-v8a")
                isUniversalApk = false
            }
        }
        release {
            signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )

            ndk {
                debugSymbolLevel = "SYMBOL_TABLE"
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.fragment.ktx)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.navigation.compose)
    // Firebase
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.auth)
    implementation(libs.firebase.database)
    implementation(libs.firebase.firestore)
    implementation(libs.firebase.messaging)
    implementation(libs.firebase.crashlytics)
    implementation(libs.datastore.preferences)
    // Credential Manager (Google Sign-In)
    implementation(libs.androidx.credentials)
    implementation(libs.androidx.credentials.play.services.auth)
    implementation(libs.googleid)
    // Image loading (Coil 3)
    implementation(libs.coil.compose)
    implementation(libs.coil.network.okhttp)
    implementation(libs.play.services.ads)
    implementation(libs.user.messaging.platform)
    implementation(libs.play.billing.ktx)
    // Pin WorkManager runtime (transitive from Ads/Messaging) to avoid old Room DB init issues
    implementation(libs.androidx.work.runtime.ktx)
    // Play In-App Updates
    implementation(libs.play.app.update.ktx)
    // Timber logging
    implementation(libs.timber)
    implementation(libs.androidx.compose.runtime)
    implementation(libs.androidx.material3)
    // Modules
    implementation(project(":domain"))
    implementation(project(":data"))
    // Hilt
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}

play {
    // Google Play Console 서비스 계정 키 파일 경로 (app 모듈 루트 기준)
    // 이 파일은 절대 git에 커밋하지 마세요! (.gitignore 추가 필수)
    serviceAccountCredentials.set(file("google-play-api-key.json"))

    // App Bundle(.aab) 사용
    defaultToAppBundles.set(true)

    // 배포 트랙: internal (비공개 테스트)
    track.set("alpha")

    // publishBundle 실행 시 즉시 배포
    releaseStatus.set(ReleaseStatus.COMPLETED)

    // 100% 배포
    userFraction.set(1.0)
}

// publishBundle 태스크가 끝난 후 incrementVersionCode 실행 (성공 여부는 태스크 내부에서 체크)
tasks.matching { it.name == "publishBundle" }.configureEach {
    finalizedBy("incrementVersionCode")
}
