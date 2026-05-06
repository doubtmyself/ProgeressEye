plugins {
    alias(libs.plugins.androidLibrary)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.chg.progeresseye.data"
    compileSdk = 36

    defaultConfig {
        minSdk = 24
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlin {
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }
}

dependencies {
    implementation(project(":domain"))
    implementation(libs.kotlinxCoroutinesCore)

    implementation(platform(libs.firebaseBom))
    implementation(libs.firebaseDatabase)
    implementation(libs.firebaseFirestore)
    implementation(libs.firebaseAuth)

    implementation(libs.roomRuntime)
    implementation(libs.roomKtx)
    implementation(libs.hiltAndroid)
    ksp(libs.roomCompiler)
    ksp(libs.hiltCompiler)

    implementation(libs.timber)

    testImplementation(libs.junit)
}
