plugins {
    id("progeresseye.android.library")
    id("progeresseye.android.hilt")
}

android {
    namespace = "com.chg.progeresseye.data"
}

dependencies {
    implementation(project(":domain"))
    implementation(libs.kotlinx.coroutines.core)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.database)
    implementation(libs.firebase.firestore)
    implementation(libs.firebase.auth)

    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    implementation(libs.timber)

    testImplementation(libs.junit)
}
