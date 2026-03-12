package com.chg.progeresseye

import android.app.Application
import com.chg.progeresseye.util.logging.TimberInit
import com.google.firebase.crashlytics.FirebaseCrashlytics

class ProgressEyeApp : Application() {

    override fun onCreate() {
        super.onCreate()

        // Logging first
        TimberInit.ensure()

        // Crashlytics collection
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = true
    }
}
