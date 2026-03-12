package com.chg.progeresseye

import android.app.Application
import com.chg.progeresseye.util.logging.TimberInit
import com.google.firebase.crashlytics.FirebaseCrashlytics
import com.google.firebase.database.FirebaseDatabase

class ProgressEyeApp : Application() {

    override fun onCreate() {
        super.onCreate()

        // Logging first
        TimberInit.ensure()

        // RTDB 오프라인 캐시 — 네트워크 끊겼을 때 마지막 데이터 유지
        FirebaseDatabase.getInstance().setPersistenceEnabled(true)

        // Crashlytics collection
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = true
    }
}
