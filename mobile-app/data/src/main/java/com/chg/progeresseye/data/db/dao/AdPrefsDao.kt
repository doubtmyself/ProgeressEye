package com.chg.progeresseye.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.chg.progeresseye.data.db.entity.AdPrefsEntity

@Dao
interface AdPrefsDao {
    @Query("SELECT * FROM ad_prefs WHERE id = 1")
    suspend fun get(): AdPrefsEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: AdPrefsEntity)

    @Query("UPDATE ad_prefs SET adFreeUntilMs = 0 WHERE id = 1")
    suspend fun clearAdFreeUntil()
}
