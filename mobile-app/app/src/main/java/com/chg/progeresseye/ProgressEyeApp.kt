package com.chg.progeresseye

import android.app.Application
import com.chg.progeresseye.util.logging.TimberInit
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class ProgressEyeApp : Application() {

    override fun onCreate() {
        super.onCreate()
        TimberInit.ensure()
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = true
    }
}
