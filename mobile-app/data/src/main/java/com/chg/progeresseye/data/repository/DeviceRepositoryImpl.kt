package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.util.CommandBuilder
import com.chg.progeresseye.data.util.FirebaseRefs
import com.chg.progeresseye.domain.model.DeviceData
import com.chg.progeresseye.domain.model.TaskData
import com.chg.progeresseye.domain.repository.DeviceRepository
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.ServerValue
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await
import timber.log.Timber
import javax.inject.Inject

/**
 * Firebase Realtime Database를 통해 연동된 PC 기기 데이터를 주고받는 저장소 구현체
 */
class DeviceRepositoryImpl @Inject constructor() : DeviceRepository {

    override fun observeDevices(uid: String): Flow<List<DeviceData>> = callbackFlow {
        Timber.d("[DeviceRepo] observeDevices callbackFlow 시작: uid=$uid")
        val deviceCache = mutableMapOf<String, DeviceData>()
        val statusCache = mutableMapOf<String, String>()
        val heartbeatCache = mutableMapOf<String, Long>()

        fun emitState() {
            val devices = deviceCache.values.map { device ->
                val rawStatus = statusCache[device.id] ?: "offline"
                val isOnline = rawStatus == "online" || rawStatus == "monitoring" || rawStatus == "sleep"
                val isMonitoring = rawStatus == "monitoring"
                val isSleeping = rawStatus == "sleep"
                val heartbeatTs = heartbeatCache[device.id] ?: 0L
                device.copy(
                    isOnline = isOnline,
                    isMonitoring = isMonitoring,
                    isSleeping = isSleeping,
                    lastSeen = heartbeatTs
                )
            }
            trySend(devices.toList())
        }

        val devicesRef = FirebaseRefs.devicesRef(uid)
        val statusRef = FirebaseRefs.deviceStatusRef(uid)

        Timber.d("[DeviceRepo] devicesRef.get() 호출 중...")
        devicesRef.get()
            .addOnSuccessListener { snapshot ->
                Timber.d("[DeviceRepo] devicesRef.get() 성공: childCount=${snapshot.childrenCount}")
                if (deviceCache.isEmpty()) {
                    snapshot.children.forEach { child ->
                        parseDevice(child)?.let { deviceCache[it.id] = it }
                    }
                }
                emitState()
            }
            .addOnFailureListener { e ->
                Timber.e(e, "[DeviceRepo] devicesRef.get() 실패")
            }

        Timber.d("[DeviceRepo] statusRef.get() 호출 중...")
        statusRef.get()
            .addOnSuccessListener { snapshot ->
                Timber.d("[DeviceRepo] statusRef.get() 성공: childCount=${snapshot.childrenCount}")
                if (statusCache.isEmpty()) {
                    snapshot.children.forEach { child ->
                        val deviceId = child.key ?: return@forEach
                        statusCache[deviceId] = child.getValue(String::class.java) ?: "offline"
                    }
                }
                emitState()
            }
            .addOnFailureListener { e ->
                Timber.e(e, "[DeviceRepo] statusRef.get() 실패")
            }

        Timber.d("[DeviceRepo] ChildEventListener 등록 중...")
        val devicesListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                Timber.d("[DeviceRepo] devices.onChildAdded: key=${snapshot.key}")
                parseDevice(snapshot)?.let { deviceCache[it.id] = it; emitState() }
            }
            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                parseDevice(snapshot)?.let { deviceCache[it.id] = it; emitState() }
            }
            override fun onChildRemoved(snapshot: DataSnapshot) {
                snapshot.key?.let { deviceCache.remove(it); emitState() }
            }
            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) = Unit
            override fun onCancelled(error: DatabaseError) {
                Timber.e("[DeviceRepo] devices ChildEventListener onCancelled: ${error.message}")
                close(error.toException())
            }
        }

        val statusListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                Timber.d("[DeviceRepo] status.onChildAdded: key=${snapshot.key} value=${snapshot.getValue(String::class.java)}")
                snapshot.key?.let { statusCache[it] = snapshot.getValue(String::class.java) ?: "offline"; emitState() }
            }
            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                snapshot.key?.let { statusCache[it] = snapshot.getValue(String::class.java) ?: "offline"; emitState() }
            }
            override fun onChildRemoved(snapshot: DataSnapshot) {
                snapshot.key?.let { statusCache.remove(it); emitState() }
            }
            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) = Unit
            override fun onCancelled(error: DatabaseError) {
                Timber.e("[DeviceRepo] status ChildEventListener onCancelled: ${error.message}")
            }
        }

        devicesRef.addChildEventListener(devicesListener)
        statusRef.addChildEventListener(statusListener)

        awaitClose {
            devicesRef.removeEventListener(devicesListener)
            statusRef.removeEventListener(statusListener)
        }
    }

    private fun parseDevice(snapshot: DataSnapshot): DeviceData? {
        val id = snapshot.key ?: return null
        val name = snapshot.child("name").getValue(String::class.java) ?: id
        val platform = snapshot.child("platform").getValue(String::class.java) ?: ""

        val tasks = snapshot.child("tasks").children.mapNotNull { taskSnap ->
            val taskId = taskSnap.key ?: return@mapNotNull null
            val progressRaw = (taskSnap.child("p").value as? Number)?.toFloat() ?: 0f
            val status = taskSnap.child("s").getValue(String::class.java) ?: "r"
            val label = taskSnap.child("l").getValue(String::class.java) ?: taskId
            TaskData(id = taskId, label = label, progress = progressRaw / 100f, status = status)
        }

        val screenshotLatest = snapshot.child("screenshots").child("latest")
        val rawUrl = screenshotLatest.child("url").getValue(String::class.java)
        val screenshotUrl = rawUrl?.takeIf {
            it.startsWith("https://firebasestorage.googleapis.com/") ||
            it.startsWith("https://progresseye-49244.firebasestorage.app/")
        }
        val screenshotTs = screenshotLatest.child("ts").getValue(Long::class.java) ?: 0L

        val statsSnap = snapshot.child("stats")
        val cpuUsage = statsSnap.child("cpu").getValue(Double::class.java)?.toFloat()
        val gpuUsage = statsSnap.child("gpu").getValue(Double::class.java)?.toFloat()
        val ramUsage = statsSnap.child("ram").getValue(Double::class.java)?.toFloat()

        return DeviceData(
            id = id, name = name, platform = platform, isOnline = false, lastSeen = 0L,
            tasks = tasks, screenshotUrl = screenshotUrl, screenshotTs = screenshotTs,
            cpuUsage = cpuUsage, gpuUsage = gpuUsage, ramUsage = ramUsage
        )
    }

    override suspend fun checkHeartbeats(uid: String) {
        val snapshot = FirebaseRefs.heartbeatRef(uid).get().await()
        val now = System.currentTimeMillis()
        val offlineUpdates = mutableMapOf<String, Any>()
        
        snapshot.children.forEach { child ->
            val deviceId = child.key ?: return@forEach
            val ts = child.getValue(Long::class.java) ?: 0L
            val isExpired = ts <= 0L || (now - ts) >= 120_000L
            if (isExpired) {
                offlineUpdates[deviceId] = "offline"
            }
        }
        if (offlineUpdates.isNotEmpty()) {
            FirebaseRefs.deviceStatusRef(uid).updateChildren(offlineUpdates).await()
        }
    }

    override suspend fun updateMobileHeartbeat(uid: String) {
        FirebaseRefs.mobileHeartbeatRef(uid).setValue(ServerValue.TIMESTAMP).await()
    }

    override suspend fun sendScreenshotCommand(uid: String, deviceId: String) {
        FirebaseRefs.commandRef(uid, "screenshot").setValue(CommandBuilder.build(deviceId)).await()
    }

    override suspend fun sendSleepCommand(uid: String, deviceId: String) {
        FirebaseRefs.commandRef(uid, "sleep").setValue(CommandBuilder.build(deviceId)).await()
    }

    override suspend fun sendShutdownCommand(uid: String, deviceId: String) {
        FirebaseRefs.commandRef(uid, "shutdown").setValue(CommandBuilder.build(deviceId)).await()
    }
}
