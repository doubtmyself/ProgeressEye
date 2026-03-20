package com.chg.progeresseye.data.db.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "session")
data class SessionEntity(
    @PrimaryKey val id: Int = 1,
    val deviceId: String,
    val sessionId: String?,
)
