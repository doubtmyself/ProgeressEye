plugins {
    id("progeresseye.kotlin.jvm.library")
}

dependencies {
    api(libs.kotlinx.coroutines.core)
    implementation("javax.inject:javax.inject:1")
}
