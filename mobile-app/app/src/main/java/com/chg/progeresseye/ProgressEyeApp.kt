package com.chg.progeresseye

import android.app.Application
import com.chg.progeresseye.BuildConfig
import com.chg.progeresseye.util.logging.TimberInit
import com.google.firebase.crashlytics.FirebaseCrashlytics
import dagger.hilt.android.HiltAndroidApp

/**
 * 애플리케이션 클래스로, 앱 수준의 초기화(Timber, Firebase Crashlytics 등)를 담당합니다.
 * Hilt를 사용한 의존성 주입의 진입점입니다.
 */
@HiltAndroidApp
class ProgressEyeApp : Application() {

    /**
     * 애플리케이션이 시작될 때 호출됩니다.
     * 로그 시스템(Timber)을 초기화하고, 디버그 모드가 아닐 때만 Crashlytics 수집을 활성화합니다.
     */
    override fun onCreate() {
        val t0 = System.currentTimeMillis()
        super.onCreate()
        TimberInit.ensure()
        timber.log.Timber.d("[Startup] Application.onCreate start: +${System.currentTimeMillis() - t0}ms")
        FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = !BuildConfig.DEBUG
        timber.log.Timber.d("[Startup] Application.onCreate end: +${System.currentTimeMillis() - t0}ms")
    }
}
