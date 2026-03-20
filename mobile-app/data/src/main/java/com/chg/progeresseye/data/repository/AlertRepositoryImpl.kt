package com.chg.progeresseye.data.repository

import com.chg.progeresseye.domain.model.AlertItem
import com.chg.progeresseye.domain.model.AlertType
import com.chg.progeresseye.domain.repository.AlertEvent
import com.chg.progeresseye.domain.repository.AlertRepository
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject

/**
 * Firebase Realtime Database를 사용하여 알림 데이터를 읽고 쓰는 [AlertRepository]의 구체화 클래스입니다.
 */
class AlertRepositoryImpl @Inject constructor() : AlertRepository {
    private val db = FirebaseDatabase.getInstance()

    override fun observeAlerts(uid: String): Flow<AlertEvent> = callbackFlow {
        val ref = db.reference.child("users").child(uid).child("alerts")
        val listener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                parse(snapshot)?.let { trySend(AlertEvent.Added(it)) }
            }
            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                parse(snapshot)?.let { trySend(AlertEvent.Changed(it)) }
            }
            override fun onChildRemoved(snapshot: DataSnapshot) {
                snapshot.key?.let { trySend(AlertEvent.Removed(it)) }
            }
            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {}
            override fun onCancelled(error: DatabaseError) {}
        }
        ref.addChildEventListener(listener)
        ref.addListenerForSingleValueEvent(object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) { trySend(AlertEvent.InitialLoadComplete) }
            override fun onCancelled(error: DatabaseError) { trySend(AlertEvent.InitialLoadComplete) }
        })
        awaitClose { ref.removeEventListener(listener) }
    }

    override fun deleteAlert(uid: String, alertId: String) {
        db.reference.child("users").child(uid).child("alerts").child(alertId).removeValue()
    }

    override fun clearAlerts(uid: String) {
        db.reference.child("users").child(uid).child("alerts").removeValue()
    }

    /**
     * Firebase RTDB의 DataSnapshot을 [AlertItem] 모델로 변환 파싱합니다.
     */
    private fun parse(snapshot: DataSnapshot): AlertItem? {
        val id = snapshot.key ?: return null
        val ts = snapshot.child("ts").getValue(Long::class.java) ?: 0L
        val title = snapshot.child("title").getValue(String::class.java) ?: ""
        val body = snapshot.child("message").getValue(String::class.java)
            ?: snapshot.child("body").getValue(String::class.java) ?: ""
        val typeStr = snapshot.child("type").getValue(String::class.java) ?: ""
        val type = try {
            if (typeStr.isNotEmpty()) AlertType.valueOf(typeStr) else AlertType.IMAGE_CHANGE
        } catch (e: Exception) {
            AlertType.IMAGE_CHANGE
        }
        val isRead = snapshot.child("isRead").getValue(Boolean::class.java) ?: false
        val deviceName = snapshot.child("deviceName").getValue(String::class.java) ?: ""
        return AlertItem(id, isRead, ts, title, body, type, deviceName)
    }
}
