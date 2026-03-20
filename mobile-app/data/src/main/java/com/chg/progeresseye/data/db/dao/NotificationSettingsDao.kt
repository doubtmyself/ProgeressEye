package com.chg.progeresseye.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.chg.progeresseye.data.db.entity.NotificationSettingsEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface NotificationSettingsDao {
    @Query("SELECT * FROM notification_settings WHERE id = 1")
    fun observe(): Flow<NotificationSettingsEntity?>

    @Query("SELECT * FROM notification_settings WHERE id = 1")
    suspend fun get(): NotificationSettingsEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: NotificationSettingsEntity)
}
