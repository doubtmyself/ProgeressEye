package com.chg.progeresseye.util.logging

import com.chg.progeresseye.BuildConfig
import timber.log.Timber

object TimberInit {
    fun ensure() {
        if (Timber.forest().isNotEmpty()) return

        val isDebug = BuildConfig.DEBUG
        if (isDebug) {
            Timber.plant(object : Timber.DebugTree() {
                override fun log(priority: Int, tag: String?, message: String, t: Throwable?) {
                    val element = findCallerStackTraceElement()
                    val prefix = "[LOG]:(${element.fileName}:${element.lineNumber})"
                    super.log(priority, tag, "$prefix $message", t)
                }

                override fun createStackElementTag(element: StackTraceElement): String? {
                    return element.fileName ?: super.createStackElementTag(element)
                }
            })

            Timber.d("Timber initialized (debug build)")
        }
    }

    private fun findCallerStackTraceElement(): StackTraceElement {
        val stackTrace = Throwable().stackTrace
        for (element in stackTrace) {
            val className = element.className
            if (className.startsWith(Timber::class.java.name)) continue
            if (className.startsWith(TimberInit::class.java.name)) continue
            if (className.startsWith("java.lang.Thread")) continue
            return element
        }
        return stackTrace.first()
    }
}
