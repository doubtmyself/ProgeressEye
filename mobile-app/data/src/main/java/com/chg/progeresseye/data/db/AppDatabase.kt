package com.chg.progeresseye.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.chg.progeresseye.data.db.dao.AdPrefsDao
import com.chg.progeresseye.data.db.dao.NotificationSettingsDao
import com.chg.progeresseye.data.db.dao.SessionDao
import com.chg.progeresseye.data.db.entity.AdPrefsEntity
import com.chg.progeresseye.data.db.entity.NotificationSettingsEntity
import com.chg.progeresseye.data.db.entity.SessionEntity

@Database(
    entities = [SessionEntity::class, NotificationSettingsEntity::class, AdPrefsEntity::class],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun sessionDao(): SessionDao
    abstract fun notificationSettingsDao(): NotificationSettingsDao
    abstract fun adPrefsDao(): AdPrefsDao
}
