package com.chg.progeresseye.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "ad_prefs")
data class AdPrefsEntity(
    @PrimaryKey val id: Int = 1,
    val adFreeUntilMs: Long = 0L,
    val adsConsented: Boolean = false,
    val isPersonalizedAds: Boolean = true,
)
