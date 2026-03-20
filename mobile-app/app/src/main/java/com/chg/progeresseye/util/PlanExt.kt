package com.chg.progeresseye.util

fun String?.isPro(): Boolean = this == "pro"

fun String?.toNormalizedPlan(): String = if (this == "pro") "pro" else "free"
