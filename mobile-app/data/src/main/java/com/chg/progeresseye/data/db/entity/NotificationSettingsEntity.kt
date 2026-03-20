package com.chg.progeresseye.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "notification_settings")
data class NotificationSettingsEntity(
    @PrimaryKey val id: Int = 1,
    val completionAlerts: Boolean = true,
    val stallWarnings: Boolean = true,
)
