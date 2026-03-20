package com.chg.progeresseye.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.chg.progeresseye.data.db.entity.SessionEntity

@Dao
interface SessionDao {
    @Query("SELECT * FROM session WHERE id = 1")
    suspend fun get(): SessionEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entity: SessionEntity)

    @Query("UPDATE session SET sessionId = NULL WHERE id = 1")
    suspend fun clearSessionId()
}
