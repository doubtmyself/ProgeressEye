package com.chg.progeresseye

import android.app.Application
import com.chg.progeresseye.BuildConfig
import com.chg.progeresseye.util.logging.TimberInit
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class ProgressEyeApp : Application() {

    override fun onCreate() {
        val t0 = System.currentTimeMillis()
        super.onCreate()
        TimberInit.ensure()
        timber.log.Timber.d("[Startup] Application.onCreate start: +${System.currentTimeMillis() - t0}ms")
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = !BuildConfig.DEBUG
        timber.log.Timber.d("[Startup] Application.onCreate end: +${System.currentTimeMillis() - t0}ms")
    }
}
